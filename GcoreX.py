"""
GcoreX V7 — Modular, Optimized Architecture.

Speed improvements:
- BrainRouter classifies every input FIRST — simple queries never hit reasoning.
- LLMEngine uses keep_alive, token budgets (60/120/350 by route), and streaming.
- ReasoningEngine has a hard 3-second timeout guard.
- pyttsx3 is lazy-loaded (only on first speak() call).
- Tool execution can run in background threads via execute_background().
"""

import os
import json
import re
import ast
import operator
import traceback
import importlib
import pkgutil
import concurrent.futures
import time
import queue
import logging
import threading
import collections
import math
from colorama import Fore, Style, init

# Initialize colorama for cross-platform colored terminal output
init(autoreset=True)

# Core modules
from core.brain_router       import BrainRouter
from core.llm_engine         import LLMEngine
from core.reasoning_engine   import ReasoningEngine
from core.tool_manager       import GcoreXToolManager
from core.memory_manager     import GcoreXMemory, GcoreXVectorMemory
from core.monitor            import GcoreXMonitor
from core.response_validator import ResponseValidator
from core.learning_engine    import LearningEngine
from core.conversation_memory import ConversationMemory

# Configure minimal logging
logging.basicConfig(level=logging.ERROR, format="%(name)s - %(levelname)s: %(message)s")
logger = logging.getLogger("GcoreX")


def log_dev(module, message):
    """Prints a colored developer log if dev_mode is enabled."""
    # We check dev_mode inside the agent, but this helper handles the colors.
    colors = {
        "router":     Fore.CYAN,
        "validator":  Fore.YELLOW,
        "correction": Fore.MAGENTA,
        "tool":       Fore.BLUE,
        "reasoning":  Fore.LIGHTBLUE_EX,
        "planner":    Fore.LIGHTGREEN_EX,
        "error":      Fore.RED
    }
    color = colors.get(module, Fore.WHITE)
    print(color + f"[DEV-{module.upper()}] {message}" + Style.RESET_ALL)


# ============================================================
# Small helper classes kept in main file (lightweight)
# ============================================================

class GcoreXGoalManager:
    """Manages persistent autonomous goals."""

    def __init__(self, file_path="goals.json"):
        self.file_path = file_path
        self.active_goals = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.active_goals = json.load(f).get("active_goals", [])
            except Exception as e:
                logger.error(f"Goal Manager Load Error: {e}")

    def save(self):
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"active_goals": self.active_goals}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception as e:
            logger.error(f"Goal Manager Save Error: {e}")

    def add_goal(self, goal):
        if goal not in self.active_goals:
            self.active_goals.append(goal)
            self.save()

    def remove_goal(self, goal):
        try:
            if goal in self.active_goals:
                self.active_goals.remove(goal)
                self.save()
                return True
        except Exception as e:
            logger.error(f"Goal Manager Remove Error: {e}")
        return False

    def list_goals(self):
        return self.active_goals


class GcoreXTaskTreeMemory:
    """Stores generated task trees and tracks completion."""

    def __init__(self, file_path="task_tree.json"):
        self.file_path = file_path
        self.goals = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.goals = json.load(f).get("goals", [])
            except Exception:
                pass

    def save(self):
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"goals": self.goals}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception:
            pass

    def save_goal_tree(self, goal, tasks):
        try:
            for g in self.goals:
                if g.get("goal") == goal:
                    g["tasks"] = [{"task": t, "status": "pending"} for t in tasks]
                    self.save()
                    return
            self.goals.append({"goal": goal, "tasks": [{"task": t, "status": "pending"} for t in tasks]})
            self.save()
        except Exception:
            pass

    def get_pending_tasks(self, goal):
        for g in self.goals:
            if g.get("goal") == goal:
                return [t["task"] for t in g.get("tasks", []) if t.get("status") == "pending"]
        return []

    def mark_task_complete(self, goal, task):
        try:
            for g in self.goals:
                if g.get("goal") == goal:
                    for t in g.get("tasks", []):
                        if t.get("task") == task:
                            t["status"] = "complete"
                            self.save()
                            return
        except Exception:
            pass


class GcoreXPlannerMemory:
    """Learns from successful plans."""

    def __init__(self, file_path="planner_memory.json"):
        self.file_path = file_path
        self.patterns = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.patterns = json.load(f).get("successful_patterns", [])
            except Exception:
                pass

    def save(self):
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"successful_patterns": self.patterns}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception:
            pass

    def get_pattern(self, goal_type):
        matches = [p for p in self.patterns if p.get("goal_type") == goal_type]
        if matches:
            matches.sort(key=lambda p: p.get("success_score", 0.0), reverse=True)
            return matches[0].get("task_sequence", [])
        return []

    def save_pattern(self, goal_type, tasks):
        try:
            for p in self.patterns:
                if p.get("goal_type") == goal_type and p.get("task_sequence") == tasks:
                    return
            self.patterns.append({
                "goal_type": goal_type,
                "task_sequence": tasks,
                "success_score": 0.5,
                "usage_count": 0,
            })
            self.save()
        except Exception:
            pass

    def update_pattern_score(self, goal_type, new_val):
        matches = [p for p in self.patterns if p.get("goal_type") == goal_type]
        if matches:
            matches.sort(key=lambda p: p.get("success_score", 0.0), reverse=True)
            p = matches[0]
            p["usage_count"] = p.get("usage_count", 0) + 1
            curr = p.get("success_score", 0.5)
            p["success_score"] = (curr * (p["usage_count"] - 1) + new_val) / p["usage_count"]
            self.save()


class GcoreXToolRecommender:
    """Tracks and recommends tools based on previous success rates."""

    def __init__(self, file_path="tool_recommendations.json"):
        self.file_path = file_path
        self.recommendations = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.recommendations = json.load(f).get("recommendations", [])
            except Exception:
                pass

    def save(self):
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"recommendations": self.recommendations}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception as e:
            logger.error(f"Tool Recommender Save Error: {e}")

    def get_recommendations(self, user_input):
        keyword = user_input.split()[0].lower() if user_input else ""
        matches = [r for r in self.recommendations if r.get("task_keyword") == keyword]
        matches.sort(key=lambda x: x.get("success_rate", 0), reverse=True)
        return matches[:3]

    def update_recommendation(self, user_input, tool_name, success):
        keyword = user_input.split()[0].lower() if user_input else ""
        if not keyword:
            return
        for r in self.recommendations:
            if r.get("task_keyword") == keyword and r.get("preferred_tool") == tool_name:
                r["usage_count"] = r.get("usage_count", 0) + 1
                curr = r.get("success_rate", 0.0)
                val = 1.0 if success else 0.0
                r["success_rate"] = (curr * (r["usage_count"] - 1) + val) / r["usage_count"]
                self.save()
                return
        self.recommendations.append({
            "task_keyword": keyword,
            "preferred_tool": tool_name,
            "success_rate": 1.0 if success else 0.0,
            "usage_count": 1,
        })
        self.save()


# ============================================================
# Intent Router (fast path for obvious commands)
# ============================================================

class GcoreXIntentRouter:
    """Fast-path regex router — avoids LLM for obvious action commands."""

    def __init__(self, tools_manager):
        self.tools = tools_manager

    def try_fast_path(self, text):
        if not text:
            return None, None

        t = text.lower().strip()
        t_clean = re.sub(r"[^\w\s]", "", t).strip()

        conversational = {
            "good", "ok", "okay", "thanks", "thank you", "nice", "great",
            "cool", "awesome", "yes", "no", "hello", "hi", "hey",
        }
        if t_clean in conversational:
            return None, None

        original = text.strip()

        if t.startswith(("open ", "launch ", "start ")):
            for p in ["open ", "launch ", "start "]:
                if t.startswith(p):
                    return "open_app", original[len(p):].strip()

        if t.startswith(("search ", "google ", "find ", "lookup ")):
            for p in ["search ", "google ", "find ", "lookup "]:
                if t.startswith(p):
                    return "search", original[len(p):].strip()

        if t.startswith(("play ", "watch ", "listen ")):
            for p in ["play ", "watch ", "listen "]:
                if t.startswith(p):
                    return "play", original[len(p):].strip()

        if t.startswith(("calculate ", "calc ", "compute ")):
            for p in ["calculate ", "calc ", "compute "]:
                if t.startswith(p):
                    return "calc", original[len(p):].strip()

        if t.startswith("run "):
            return "run", original[4:].strip()

        return None, None


# ============================================================
# Planner
# ============================================================

class GcoreXPlanner:
    """Breaks down complex tasks into executable steps."""

    def __init__(self, agent):
        self.agent = agent

    def score_priority(self, task):
        task = task.lower()
        if any(k in task for k in ["research", "analyze", "investigate"]):
            return 10
        if any(k in task for k in ["search", "collect", "find"]):
            return 8
        if any(k in task for k in ["write", "generate", "create"]):
            return 6
        if any(k in task for k in ["summarize", "compile"]):
            return 5
        return 3

    def detect_goal_type(self, text):
        t = text.lower()
        if "research" in t:
            return "research"
        if "code" in t or "script" in t:
            return "coding"
        if "write" in t or "draft" in t:
            return "writing"
        return "general"

    def check_and_plan(self, user_input):
        t = user_input.lower().strip()
        if not (t.startswith("plan ") or t.startswith("research ")):
            return False

        goal_type = self.detect_goal_type(t)
        pattern = self.agent.planner_memory.get_pattern(goal_type)
        pattern_str = (
            f"Use this successful pattern as a guide:\n{json.dumps(pattern)}\n" if pattern else ""
        )

        prompt = f"""
You are the Task Planner. The user wants to: "{user_input}"
Break this task into a structured hierarchy of steps. {pattern_str}
Return ONLY a valid JSON format object matching this structure:
{{
 "goal": "description",
 "tasks": [
   {{"task": "step 1", "subtasks": ["subtask A", "subtask B"]}},
   {{"task": "step 2", "subtasks": []}}
 ]
}}
Do not include markdown or explanations. Use available tools.
"""
        for _ in range(2):
            raw = self.agent.llm.ask(prompt, route="planning_task", show_thinking=True)
            try:
                # Find outer { }
                s, e = raw.find("{"), raw.rfind("}")
                if s != -1 and e > s:
                    plan_data = json.loads(raw[s:e + 1])
                else:
                    continue

                if not isinstance(plan_data, dict) or "tasks" not in plan_data:
                    continue

                if self.agent.dev_mode:
                    log_dev("planner", f"Task Tree:\n{json.dumps(plan_data, indent=2)}")

                flattened = []

                def flatten_tree(nodes, depth=1):
                    if depth > 3 or len(flattened) >= 10:
                        return
                    for node in nodes:
                        if len(flattened) >= 10:
                            break
                        if isinstance(node, dict):
                            if "task" in node and node["task"]:
                                flattened.append(node["task"])
                            subs = node.get("subtasks", [])
                            if isinstance(subs, list):
                                for sub in subs:
                                    if len(flattened) >= 10:
                                        break
                                    if isinstance(sub, str):
                                        flattened.append(sub)
                                    elif isinstance(sub, dict):
                                        flatten_tree([sub], depth + 1)
                        elif isinstance(node, str):
                            flattened.append(node)

                flatten_tree(plan_data["tasks"])

                final_steps = []
                for s_item in flattened:
                    if s_item not in final_steps and not s_item.lower().startswith(("plan ", "research ")):
                        final_steps.append(s_item)
                final_steps = list(dict.fromkeys(final_steps))[:10]

                self.agent.speak(f"Planner activated. Flattened into {len(final_steps)} tasks.")

                actual_goal = (
                    user_input[5:].strip()
                    if user_input.lower().startswith("plan ")
                    else user_input[9:].strip()
                )
                if actual_goal:
                    self.agent.task_tree.save_goal_tree(actual_goal, final_steps)
                self.agent.planner_memory.save_pattern(goal_type, final_steps)

                for i, step in enumerate(final_steps):
                    with self.agent.queue_lock:
                        if step not in self.agent.queued_tasks:
                            priority = self.score_priority(step)
                            self.agent.tool_queue.put((priority * -1, step))
                            self.agent.queued_tasks.add(step)
                            self.agent.speak(f"Queuing Step {i + 1}: {step}")
                return True

            except Exception as e:
                logger.error(f"Planner parsing failed: {e}")

        return False


# ============================================================
# Memory Compressor
# ============================================================

class GcoreXMemoryCompressor:
    """Summarizes older conversations into compressed knowledge."""

    def __init__(self, agent):
        self.agent = agent

    def check_and_compress(self):
        if len(self.agent.memory.history) > 20:
            oldest = self.agent.memory.history[:10]
            self.agent.memory.history = self.agent.memory.history[10:]
            self.agent.memory.save()

            if self.agent.dev_mode:
                log_dev("reasoning", "Compressing 10 oldest memory interactions...")

            context = "\n".join(
                [f"User: {m.get('user', '')}\nGcoreX: {m.get('gcorex', '')}" for m in oldest]
            )
            prompt = (
                f"Summarize these past 10 interactions into a single concise factual statement. "
                f"Focus on the core topic, facts, and user preferences. Return EXACTLY one sentence:\n{context}"
            )
            summary = self.agent.llm.ask(prompt, route="fast_chat", show_thinking=False)
            if summary:
                self.agent.vector_memory.add_knowledge("[Conversation Summary] " + summary.strip())


# ============================================================
# Multi-agent wrappers
# ============================================================

class PlannerAgent:
    def __init__(self, planner): self.planner = planner
    def plan(self, goal): return self.planner.check_and_plan(goal)


class ExecutorAgent:
    def __init__(self, tool_manager): self.tools = tool_manager
    def execute(self, action, value, timeout=15): return self.tools.execute(action, value, timeout=timeout)
    def execute_background(self, action, value, timeout=15): return self.tools.execute_background(action, value, timeout)


class MemoryAgent:
    def __init__(self, vector_memory): self.memory = vector_memory
    def store(self, text): self.memory.add_knowledge(text)
    def retrieve(self, query): return self.memory.search_knowledge(query)


class ResearchAgent:
    def __init__(self, executor, memory_agent, core_agent):
        self.executor = executor
        self.memory = memory_agent
        self.core = core_agent

    def research(self, topic):
        self.core.speak(f"Research Agent starting deep dive on: {topic}")
        search_res = self.executor.execute("search", topic, timeout=20)
        if not search_res or "Error" in str(search_res):
            self.core.speak("Research Agent failed to find information.")
            return "Research Failed"

        self.core.speak("Synthesizing research data...")
        prompt = f"Summarize the following research data into 3 key points. Data: {str(search_res)[:1500]}"
        summary = self.core.llm.ask(prompt, route="reasoning_required", show_thinking=False)
        self.memory.store(f"Research on {topic}: {summary}")
        self.core.speak("Research complete. Saved to long-term memory.")
        return summary


class GcoreXAgentSystem:
    """Lightweight orchestrator for multi-agent capabilities."""

    def __init__(self, core_agent):
        self.planner = PlannerAgent(core_agent.planner)
        self.executor = ExecutorAgent(core_agent.tools)
        self.memory = MemoryAgent(core_agent.vector_memory)
        self.researcher = ResearchAgent(self.executor, self.memory, core_agent)


# ============================================================
# JSON helpers
# ============================================================

def extract_json_object(text):
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            pass

    return None


# ============================================================
# Main Agent
# ============================================================

class GcoreXAgent:
    """The main AI Core — V7 optimized modular architecture."""

    def __init__(
        self,
        model: str = "mistral",
        ollama_url: str = "http://localhost:11434/api/generate",
        speak_output: bool = True,
    ):
        self.model = model
        self.url = ollama_url
        self.dev_mode = False

        # Core modules
        host = ollama_url.replace("/api/generate", "")
        self.llm            = LLMEngine(model=model, host=host)
        self.brain_router   = BrainRouter()
        self.memory         = GcoreXMemory()
        self.conv_memory    = ConversationMemory(max_messages=8)
        self.vector_memory  = GcoreXVectorMemory()
        self.tools          = GcoreXToolManager()
        self.monitor        = GcoreXMonitor()
        self.reasoning_engine = ReasoningEngine(self)
        self.validator      = ResponseValidator()
        self.learning       = LearningEngine()

        # Higher-level systems
        self.goal_manager   = GcoreXGoalManager()
        self.task_tree      = GcoreXTaskTreeMemory()
        self.planner_memory = GcoreXPlannerMemory()
        self.planner        = GcoreXPlanner(self)
        self.compressor     = GcoreXMemoryCompressor(self)
        self.recommender    = GcoreXToolRecommender()
        self.router         = GcoreXIntentRouter(self.tools)
        self.system         = GcoreXAgentSystem(self)

        # Queues and state
        self.tool_queue         = queue.PriorityQueue()
        self.queue_lock         = threading.Lock()
        self.queued_tasks:set   = set()
        self.request_timestamps = []
        self.tool_cache         = collections.OrderedDict()
        self.tool_cache_lock    = threading.Lock()
        self.recent_tool_calls  = []

        # Background post-processing worker
        self.post_queue = queue.Queue()
        self.post_worker = threading.Thread(target=self._post_process_worker, daemon=True)
        self.post_worker.start()

        # Background goal worker
        self.background_running = True
        self.background_thread = threading.Thread(target=self._background_goal_worker, daemon=True)
        self.background_thread.start()

        # Lazy TTS — only init on first speak()
        self.speak_output = speak_output
        self._tts_engine = None
        self._tts_lock = threading.Lock()

    # ------------------------------------------------------------------
    # TTS — lazy init
    # ------------------------------------------------------------------

    def _get_tts(self):
        if self._tts_engine is not None:
            return self._tts_engine
        with self._tts_lock:
            if self._tts_engine is None:
                try:
                    import pyttsx3
                    self._tts_engine = pyttsx3.init()
                except Exception as e:
                    logger.error(f"Failed to init TTS: {e}")
                    self.speak_output = False
        return self._tts_engine

    def speak(self, text):
        if not text:
            return
        text_str = str(text)

        # Only print if it hasn't been printed already (e.g., via streaming)
        # Note: We check if the last few lines of stdout contain the text, 
        # but a simpler way is to just use a skip_print flag if we were more complex.
        # For now, we'll just check if it's already visible.
        # However, to keep it simple and robust, we'll just add a parameter.
        pass

    def speak(self, text, already_printed=False):
        if not text:
            return
        text_str = str(text)
        
        if not already_printed:
            print(Fore.GREEN + f"GcoreX: {text_str}" + Style.RESET_ALL)

    def _speak_tts(self, text):
        """Internal method for background TTS to avoid blocking the main loop."""
        if not self.speak_output or not text:
            return
        try:
            eng = self._get_tts()
            if eng:
                eng.say(str(text)[:250])
                eng.runAndWait()
        except Exception as e:
            logger.error(f"TTS Error: {e}")

    # ------------------------------------------------------------------
    # Legacy Ollama shim — keeps old call sites working
    # ------------------------------------------------------------------

    def _ask_ollama_streaming(self, prompt, retries=2, timeout=60, show_thinking=True):
        return self.llm.ask(
            prompt,
            route="reasoning_required",
            stream_to_stdout=False,
            retries=retries,
            timeout=timeout,
            show_thinking=show_thinking,
        )

    # ------------------------------------------------------------------
    # Startup banner
    # ------------------------------------------------------------------

    def print_startup_banner(self):
        print(Fore.CYAN + "=" * 50)
        print(Fore.CYAN + "🤖 " + Fore.WHITE + Style.BRIGHT + "GcoreX V7 — Modular Optimized Architecture")
        print(Fore.CYAN + "=" * 50)
        print(f"[*] {Fore.LIGHTBLACK_EX}Model          : {Fore.WHITE}{self.model}")
        conn_status = Fore.GREEN + "Online" if self.llm.ping() else Fore.RED + "Offline (start Ollama!)"
        print(f"[*] {Fore.LIGHTBLACK_EX}Connection     : {conn_status}")
        print(f"[*] {Fore.LIGHTBLACK_EX}Loaded Tools   : {Fore.WHITE}{len(self.tools.modules)} active plugins")
        print(f"[*] {Fore.LIGHTBLACK_EX}Memory History : {Fore.WHITE}{len(self.memory.history)}/{self.memory.max_history}")
        print(f"[*] {Fore.LIGHTBLACK_EX}Active Goals   : {Fore.WHITE}{len(self.goal_manager.active_goals)} pending")
        print(Fore.CYAN + "=" * 50)
        print(Fore.YELLOW + "Ready. (type 'exit', 'dev mode on/off', 'sys monitor')\n")

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _generate_prompt(self, user_input, extra_context=""):
        context = self.memory.get_context_string(limit=5)
        retrieved_facts = self.vector_memory.search_knowledge(user_input, top_k=4)
        fact_str = "\n".join([f"- {f}" for f in retrieved_facts]) if retrieved_facts else "No match."
        extra_context += f"\n[Relevant Long-Term Memory]:\n{fact_str}\n"

        summaries = [
            k["text"] for k in self.vector_memory.knowledge
            if k["text"].startswith("[Conversation Summary]")
        ]
        sum_str = "\n".join([f"- {s.replace('[Conversation Summary] ', '')}" for s in summaries[-3:]]) or "None."
        extra_context += f"\n[Conversation Summary Memory]:\n{sum_str}\n"

        recs = self.recommender.get_recommendations(user_input)
        if recs:
            rec_str = "\n".join([f"* {r['preferred_tool']} ({int(r['success_rate'] * 100)}%)" for r in recs])
            extra_context += f"\n[Tool Recommendation Memory]:\n{rec_str}\n"

        if len(context) > 2000:
            context = "..." + context[-1997:]

        tool_desc = self.tools.get_descriptions()

        return f"""
You are GcoreX, a smart AI companion.

PERSONALITY:
- Natural, concise, slightly casual but highly intelligent.
- If the user gives casual feedback ("good bro", "nice"), reply briefly and naturally.

CRITICAL RULES:
1. Analyze intent first. Correct typos mentally.
2. Complex/multi-step goal → action "auto", value = goal.
3. Simple physical/system action → select the correct tool.
4. Conversational → action "chat".
5. Confidence < 0.65 → fallback to "chat".
6. Only the CURRENT user message determines tool use. Do not repeat previous commands.

Available Actions:
- "auto": For complex goals, multi-step tasks, research, writing.
{tool_desc}

{extra_context}

Return ONLY a JSON array:
[
{{
  "reasoning": "...",
  "confidence": 0.9,
  "action": "chat",
  "value": "",
  "response": "..."
}}
]

Recent Context:
{context}

User: {user_input}
"""

    # ------------------------------------------------------------------
    # Parse intents
    # ------------------------------------------------------------------

    def _parse_intents(self, text):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return [parsed]
            if isinstance(parsed, list):
                return [d for d in parsed if isinstance(d, dict)]
        except Exception:
            pass

        valid = []
        for m in re.findall(r"\[.*?\]|\{.*?\}", text, re.DOTALL):
            try:
                parsed = json.loads(m)
                if isinstance(parsed, dict):
                    valid.append(parsed)
                elif isinstance(parsed, list):
                    valid.extend([d for d in parsed if isinstance(d, dict)])
            except Exception:
                pass

        return valid

    # ------------------------------------------------------------------
    # Word-count pre-detection helpers
    # ------------------------------------------------------------------

    def _get_word_count_num_predict(self, user_input: str) -> int:
        """
        If the user requested a specific word count, return an appropriate
        num_predict override (word_target * 1.8, capped at 1200).
        Returns 0 if no word-count instruction is detected.
        """
        target = self.validator.get_word_count_target(user_input)
        if target and target > 0:
            return min(int(target * 1.8), 1200)
        return 0

    def _build_correction_prompt(self, user_input: str, bad_response: str, reason: str, hint: str) -> str:
        """Build the silent correction prompt sent back to the LLM."""
        return (
            f"Your previous answer did not fully satisfy the user's request.\n"
            f"Reason: {reason}\n"
            f"User request: {user_input}\n"
            f"Previous answer: {bad_response}\n\n"
            f"Rewrite the answer correctly. {hint.capitalize()}.\n"
            f"Important: only return the improved answer — no JSON, no explanations, no apologies."
        )

    def _validate_and_correct(self, user_input: str, response: str,
                              route: str = "self_correction") -> str:
        """
        Run the ResponseValidator; if the response fails, perform one silent
        correction pass and record the mistake in LearningEngine.

        Returns the (possibly corrected) response string.
        """
        is_valid, reason, hint = self.validator.validate(user_input, response)

        if is_valid:
            return response

        if self.dev_mode:
            log_dev("validator", f"FAIL — {reason}")
            log_dev("correction", f"hint: {hint}")

        # Record in learning memory
        target = self.validator.get_word_count_target(user_input)
        trigger = f"{target} words" if target else reason.split()[0]  # best trigger keyword
        self.learning.record_correction(trigger, hint)

        # Build the correction call budget
        num_predict = self._get_word_count_num_predict(user_input)
        if num_predict == 0:
            num_predict = 600   # default generous budget for correction

        correction_prompt = self._build_correction_prompt(user_input, response, reason, hint)
        corrected = self.llm.ask(
            correction_prompt,
            route=route,
            stream_to_stdout=False,
            show_thinking=self.dev_mode,
            num_predict_override=num_predict,
        ).strip()

        if not corrected:
            return response   # fallback: return original if correction also failed

        if self.dev_mode:
            orig_wc = len(response.split())
            new_wc  = len(corrected.split())
            log_dev("correction", f"Complete: {orig_wc} words → {new_wc} words")

        return corrected

    # ------------------------------------------------------------------
    # Self-correction
    # ------------------------------------------------------------------

    def self_correct(self, user_input, reasoning, response):
        if not response or not str(response).strip():
            return {"confidence": 1.0, "improved_response": response}

        prompt = f"""You are reviewing your own answer.
User Question: {user_input}
Reasoning: {reasoning}
Draft Response: {response}

Check for: logical errors, missing info, incorrect assumptions.
If the answer is good, return it unchanged.

Return JSON:
{{
  "confidence": 0.0-1.0,
  "improved_response": "corrected or original answer"
}}
"""
        for _ in range(2):
            raw = self.llm.ask(prompt, route="reasoning_required", show_thinking=self.dev_mode)
            try:
                for m in re.findall(r"\{.*?\}", raw, re.DOTALL):
                    parsed = json.loads(m)
                    if "confidence" in parsed and "improved_response" in parsed:
                        return parsed
            except Exception:
                pass
        return {"confidence": 1.0, "improved_response": response}

    # ------------------------------------------------------------------
    # Main process() — the optimized heart of GcoreX
    # ------------------------------------------------------------------

    def process(self, user_input: str, is_step: bool = False, token_callback: callable = None) -> str:
        if not user_input.strip():
            return ""

        t = user_input.lower().strip()

        # ── BrainRouter: classify FIRST ──────────────────────────────
        brain_route = self.brain_router.classify(user_input)
        if self.dev_mode:
            log_dev("router", f"BrainRouter → '{brain_route}'")

        # ── Admin commands ────────────────────────────────────────────
        if t == "reload tools":
            self.tools._load_plugins()
            resp = "Tools reloaded successfully."
            self.speak(resp)
            return resp

        if t == "dev mode on":
            self.dev_mode = True
            resp = "Developer mode enabled."
            self.speak(resp)
            return resp

        if t == "dev mode off":
            self.dev_mode = False
            resp = "Developer mode disabled."
            self.speak(resp)
            return resp

        if t == "correction":
            print(Fore.MAGENTA + f"\nLearning rules:\n{self.learning.summary_str()}")
            return "Rules displayed"

        if t == "clear memory":
            self.conv_memory.clear()
            resp = "Conversation memory cleared."
            self.speak(resp)
            return resp

        if t == "sys monitor":
            conn = Fore.GREEN + "Online" if self.llm.ping() else Fore.RED + "Offline"
            self.monitor.display(len(self.memory.history), len(self.tools.modules), self.model, conn)
            return "Monitor displayed"

        if t == "tool health":
            if self.dev_mode:
                report = self.tools.get_tool_health_report()
                log_dev("tool", f"Tool Health:\n{report}")
                return report
            resp = "Tool health is only available in DEV mode."
            self.speak(resp)
            return resp

        # ── Rate limiter ──────────────────────────────────────────────
        now = time.time()
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60]
        if len(self.request_timestamps) >= 20:
            msg = "Rate limit exceeded. Max 20 requests/min."
            self.speak(msg)
            return msg
        self.request_timestamps.append(now)

        # ── Hard-coded multi-agent intents ────────────────────────────
        if t.startswith("remember "):
            val = user_input[9:].strip()
            self.system.memory.store(val)
            resp = "I've stored that in long-term memory."
            self.speak(resp)
            return resp

        if t.startswith("forget "):
            val = user_input[7:].strip()
            cleared = self.vector_memory.forget_knowledge(val)
            resp = "Knowledge forgotten." if cleared else "No matching knowledge found."
            self.speak(resp)
            return resp

        if t.startswith("knowledge search "):
            val = user_input[17:].strip()
            results = self.system.memory.retrieve(val)
            resp = (
                f"Found {len(results)} entries:\n" + "\n".join(results)
                if results
                else "I don't remember anything about that."
            )
            self.speak(resp)
            return resp

        if t.startswith("research "):
            topic = user_input[9:].strip()
            return self.system.researcher.research(topic)

        if t == "goals":
            active = self.goal_manager.list_goals()
            resp = "Active Goals:\n" + "\n".join([f"- {g}" for g in active]) if active else "No active goals."
            self.speak(resp)
            return resp

        if t == "clear goals":
            self.goal_manager.active_goals = []
            self.goal_manager.save()
            resp = "All goals cleared."
            self.speak(resp)
            return resp

        if t.startswith("auto "):
            goal = user_input[5:].strip()
            self.speak(f"Autonomous Mode Initiated. Goal: {goal}")
            threading.Thread(target=self._execute_goal_background, args=(goal,), daemon=True).start()
            return "Autonomous loop started."

        # ── BrainRouter: fast_chat shortcut ──────────────────────────
        # Uses a plain-text prompt (NOT JSON) so there is nothing to parse —
        # the raw LLM output IS the user-facing response. This eliminates
        # JSON field leaking entirely and is faster (fewer tokens needed).
        if brain_route == "fast_chat" and not is_step:
            t0 = time.time()
            
            # 1. Build context safely
            messages = [{"role": "system", "content": "You are GcoreX, a helpful and concise AI assistant."}]
            
            history = self.conv_memory.get_recent_context()
            if isinstance(history, list):
                messages.extend(history)
            
            messages.append({"role": "user", "content": user_input})

            # 2. Bump token budget if needed
            _num_predict_override = self._get_word_count_num_predict(user_input)

            # 3. Call LLM with streaming ENABLED
            resp = self.llm.chat(
                messages,
                route="fast_chat",
                label=Fore.GREEN + "GcoreX: " + Style.RESET_ALL,
                show_thinking=self.dev_mode,
                num_predict_override=_num_predict_override,
                stream_to_stdout=True,  # CRITICAL: Must be True for user to see it!
                token_callback=token_callback
            ).strip()

            # 4. Clean and validate
            resp = re.sub(r'^[\[{"\s]+|[\]}"]+$', '', resp).strip()
            if not resp:
                resp = "Got it!"

            if self.dev_mode:
                log_dev("router", f"fast_chat plain response: {resp}")

            self.monitor.log_latency(time.time() - t0)
            self.speak(resp, already_printed=True)
            self.post_queue.put((user_input, resp))
            return resp

        # ── Math shortcut ─────────────────────────────────────────────
        # Catches expressions like "what is 1+2", "5*6", "10/2" anywhere
        # in the input and routes them directly to the calc tool — no LLM needed.
        _math_match = re.search(r'(\d+(?:\.\d+)?)\s*([\+\-\*/])\s*(\d+(?:\.\d+)?)', user_input)
        if _math_match and "calc" in self.tools.modules:
            expr = _math_match.group(0)
            if self.dev_mode:
                log_dev("tool", f"Math shortcut: evaluating '{expr}'")
            try:
                tool_res = self.system.executor.execute("calc", expr)
                if tool_res and "Error" not in str(tool_res):
                    self.speak(str(tool_res))
                    self.memory.add_interaction(user_input, str(tool_res))
                    return str(tool_res)
            except Exception as e:
                logger.error(f"Math shortcut error: {e}")

        # ── Fast-path intent router (tool_command) ────────────────────
        fast_action, fast_val = self.router.try_fast_path(user_input)
        if fast_action:
            if self.dev_mode:
                log_dev("router", f"Fast-Path Router: {fast_action} → {fast_val}")
            try:
                tool_res = self.system.executor.execute(fast_action, fast_val)
            except Exception as e:
                logger.error(f"Router tool error: {e}")
                tool_res = f"Error executing {fast_action}"
            if tool_res is not None:
                self.speak(str(tool_res))
                self.memory.add_interaction(user_input, str(tool_res))
                return str(tool_res)

        # ── Planner hook ──────────────────────────────────────────────
        if not is_step and self.planner.check_and_plan(user_input):
            return "Plan Executed"

        # ── Reasoning Engine pipeline ─────────────────────────────────
        t0 = time.time()

        retrieved_facts = self.vector_memory.search_knowledge(user_input, top_k=3)
        fact_context = ("\nRelevant Knowledge:\n" + "\n".join(retrieved_facts)) if retrieved_facts else ""
        
        # Use full conversation history for reasoning context
        history_str = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in self.conv_memory.get_recent_context()])
        context = history_str + fact_context
        tools_desc = self.tools.get_descriptions()

        # think() has its own internal 3-second timeout
        think_res = self.reasoning_engine.think(user_input, context, tools_desc)

        # Normalise think result
        defaults = {"intent": "Chat", "goal": "", "tool": "", "confidence": 1.0, "reasoning": "", "response": ""}
        if not isinstance(think_res, dict):
            think_res = defaults.copy()
        else:
            for k, v in defaults.items():
                if k not in think_res:
                    think_res[k] = v

        if think_res["intent"] not in {"Chat", "Action", "Plan"}:
            think_res["intent"] = "Chat"

        intent    = think_res["intent"]
        goal      = think_res.get("goal", "")
        tool      = str(think_res.get("tool", "")).strip().lower()
        response  = think_res.get("response", "")
        reasoning = think_res.get("reasoning", "")

        # ── Deep self-correction (LLM-scored) ────────────────────────
        correct_eval = self.self_correct(user_input, reasoning, response)
        try:
            c_score = float(correct_eval.get("confidence", 1.0))
        except (ValueError, TypeError):
            c_score = 1.0
        if c_score < 0.7:
            response = correct_eval.get("improved_response", response)
            if self.dev_mode:
                log_dev("correction", f"triggered (conf={c_score})")

        # ── Rule-based Validator pass (word-count / list / summary) ──
        _num_predict_override = self._get_word_count_num_predict(user_input)
        response = self._validate_and_correct(user_input, response, route="self_correction")

        # Confidence guard
        try:
            confidence = float(think_res.get("confidence", 1.0))
        except (ValueError, TypeError):
            confidence = 1.0
        if confidence < 0.6:
            intent = "Chat"

        # Hallucination guard
        if tool not in self.tools.modules and tool != "auto":
            tool = "chat"

        if self.dev_mode:
            log_dev("reasoning", f"Reasoning : {reasoning}")
            log_dev("reasoning", f"Intent={intent} | Goal={goal} | Tool={tool} | Conf={confidence}")

        final_responses = []

        # Conversational guard
        t_clean = re.sub(r"[^\w\s]", "", user_input.lower()).strip()
        conv = {"good","ok","okay","thanks","thank you","nice","great","cool","awesome","yes","no","hello","hi","hey"}
        if t_clean in conv:
            intent = "Chat"

        # ── Chat ─────────────────────────────────────────────────────
        if intent == "Chat":
            if not response:
                response = "I understand."
            self.speak(response)
            final_responses.append(response)

        # ── Action ───────────────────────────────────────────────────
        elif intent == "Action":
            current_call = f"{tool}:{goal}"
            if self.recent_tool_calls.count(current_call) > 2:
                intent = "Chat"
                response = "I've already tried that action several times. It seems I'm in a loop."
                self.speak(response)
                return response

            self.recent_tool_calls.append(current_call)
            if len(self.recent_tool_calls) > 5:
                self.recent_tool_calls.pop(0)

            if not goal or not str(goal).strip():
                response = "I need more information before executing that."
                self.speak(response)
                return response

            if self.tools.get_tool_success_rate(tool) < 0.3:
                tool = "chat"

            if tool in self.tools.modules:
                t_tool_0 = time.time()
                timeout_val = 60 if tool in ["read_file", "summarize_file", "analyze_code"] else 15
                try:
                    cache_key = f"{tool}:{goal}"
                    with self.tool_cache_lock:
                        if cache_key in self.tool_cache:
                            tool_result = self.tool_cache[cache_key]
                        else:
                            tool_result = self.system.executor.execute(tool, goal, timeout=timeout_val)
                            self.tool_cache[cache_key] = tool_result
                            if len(self.tool_cache) > 200:
                                self.tool_cache.popitem(last=False)

                    run_time = time.time() - t_tool_0
                    if tool_result is not None:
                        self.monitor.log_tool(run_time, failed=False)
                        self.recommender.update_recommendation(user_input, tool, True)

                        ref = self.reasoning_engine.reflect(goal, f"Execute {tool}", str(tool_result))
                        if self.dev_mode:
                            log_dev("reasoning", f"Reflection: {ref.get('reflection')} (success={ref.get('success')})")

                        tool_res_str = str(tool_result)
                        if len(tool_res_str) < 500:
                            critic_eval = self.reasoning_engine.critic(tool_res_str, reasoning)
                            if self.dev_mode:
                                log_dev("validator", f"Critic: score={critic_eval.get('quality_score')} issues={critic_eval.get('issues')}")
                            try:
                                score = float(critic_eval.get("quality_score", 1.0))
                            except (ValueError, TypeError):
                                score = 1.0
                            if score < 0.7:
                                tool_res_str = critic_eval.get("improved_response", tool_res_str)
                            self.speak(tool_res_str)
                        final_responses.append(tool_res_str)

                except Exception as e:
                    run_time = time.time() - t_tool_0
                    self.monitor.log_tool(run_time, failed=True)
                    self.recommender.update_recommendation(user_input, tool, False)
                    logger.error(f"Tool execution failure: {e}")
                    self.speak(f"Error executing {tool}.")
                    final_responses.append(f"Error executing {tool}.")

            elif tool == "auto":
                self.speak(f"Goal detected: {goal}. Initiating background planner.")
                threading.Thread(target=self._execute_goal_background, args=(goal,), daemon=True).start()
                final_responses.append(f"Autonomous loop started for: {goal}")
            else:
                self.speak(f"Tool '{tool}' not found.")
                final_responses.append(f"Tool '{tool}' not found.")

        # ── Plan ──────────────────────────────────────────────────────
        elif intent == "Plan":
            self.speak(f"Planning tasks for: {goal}")
            tasks = self.reasoning_engine.plan(goal, tools_desc)
            if self.dev_mode:
                log_dev("planner", f"Plan Tasks:\n{json.dumps(tasks, indent=2)}")

            task_outputs = []
            for t_item in tasks:
                t_desc = t_item.get("description", "")
                t_tool = t_item.get("suggested_tool", "chat")
                self.speak(f"Executing: {t_desc}")

                if t_tool in self.tools.modules:
                    t_tool_0 = time.time()
                    timeout_val = 60 if t_tool in ["read_file", "summarize_file", "analyze_code"] else 15
                    try:
                        tool_result = self.system.executor.execute(t_tool, f"{goal}: {t_desc}", timeout=timeout_val)
                        run_time = time.time() - t_tool_0
                        if tool_result is not None:
                            self.monitor.log_tool(run_time, failed=False)
                            self.recommender.update_recommendation(user_input, t_tool, True)
                            ref = self.reasoning_engine.reflect(goal, t_desc, str(tool_result))
                            if self.dev_mode:
                                log_dev("reasoning", f"Reflection: {ref.get('reflection')} (success={ref.get('success')})")
                            task_outputs.append((t_desc, str(tool_result)))
                            if not ref.get("success", True):
                                self.speak(f"Step '{t_desc}' did not meet expectations.")
                    except Exception as e:
                        run_time = time.time() - t_tool_0
                        self.monitor.log_tool(run_time, failed=True)
                        self.recommender.update_recommendation(user_input, t_tool, False)
                        logger.error(f"Task execution failure: {e}")

                self.task_tree.mark_task_complete(goal, t_desc)

            outputs_str = "\n".join([f"Step: {d}\nOutput: {o[:200]}" for d, o in task_outputs])
            summary_prompt = f"Goal: {goal}\nPartial Outputs:\n{outputs_str}\nSummarize the final results clearly."
            final_res = self.llm.ask(summary_prompt, route="reasoning_required", show_thinking=False)

            critic_eval = self.reasoning_engine.critic(final_res, reasoning)
            if self.dev_mode:
                log_dev("validator", f"Critic: score={critic_eval.get('quality_score')}")
            try:
                score = float(critic_eval.get("quality_score", 1.0))
            except (ValueError, TypeError):
                score = 1.0
            if score < 0.7:
                final_res = critic_eval.get("improved_response", final_res)

            self.speak(final_res)
            final_responses.append(final_res)

        # ── Wrap up ───────────────────────────────────────────────────
        self.monitor.log_latency(time.time() - t0)

        joined = " / ".join(final_responses).strip()
        if not joined:
            joined = "I processed that, but the response was empty."
        if len(joined) > 4000:
            joined = joined[:4000] + "... [Truncated]"
        if self.memory.history and joined == self.memory.history[-1].get("gcorex"):
            joined = "I just said that, but yes — " + joined.lower()

        self.post_queue.put((user_input, joined))
        return joined

    # ------------------------------------------------------------------
    # Background workers
    # ------------------------------------------------------------------

    def _post_process_worker(self):
        while True:
            try:
                user_input, response = self.post_queue.get()
                self._post_process(user_input, response)
            except Exception as e:
                logger.error(f"Post-process worker error: {e}")

    def _post_process(self, user_input, response):
        try:
            # Move memory and context building to background
            self.memory.add_interaction(user_input, response)
            self.conv_memory.add_message("user", user_input)
            self.conv_memory.add_message("assistant", response)
            
            # Background TTS
            self._speak_tts(response)
            
            self.compressor.check_and_compress()
            if len(response) > 120 and response.count(".") >= 2:
                with self.vector_memory.knowledge_lock:
                    should_store = response.strip() not in self.vector_memory.knowledge_text_index
                if should_store:
                    self.vector_memory.add_knowledge(response)
        except Exception as e:
            logger.error(f"Post-processing error: {e}")

    def _execute_goal_background(self, goal):
        self.goal_manager.add_goal(goal)
        step_count = 0
        max_steps = 10
        executed: set = set()

        pending = self.task_tree.get_pending_tasks(goal)
        if pending:
            with self.queue_lock:
                for step in pending:
                    if step not in self.queued_tasks:
                        pri = self.planner.score_priority(step)
                        self.tool_queue.put((pri * -1, step))
                        self.queued_tasks.add(step)
        else:
            self.planner.check_and_plan("plan " + goal)

        while step_count < max_steps:
            with self.queue_lock:
                if self.tool_queue.empty():
                    break
                priority, step = self.tool_queue.get(False)
                self.queued_tasks.discard(step)

            if self.dev_mode:
                log_dev("planner", f"Task priority {abs(priority)} → {step}")

            if step in executed:
                continue
            executed.add(step)

            self.speak(f"Auto-Executing: {step}")
            res = self.process(step, is_step=True)
            if res:
                pass  # could accumulate auto_responses here if needed
            self.task_tree.mark_task_complete(goal, step)
            step_count += 1

            if self.dev_mode:
                log_dev("planner", f"Queue: {self.tool_queue.qsize()} left | Steps: {step_count}/{max_steps}")

        with self.queue_lock:
            is_empty = self.tool_queue.empty()

        if not is_empty:
            self.speak("Autonomous loop reached step limit. Paused.")
            new_val = 0.5
        else:
            self.goal_manager.remove_goal(goal)
            self.speak(f"Goal completed: {goal}")
            new_val = 1.0

        self.planner_memory.update_pattern_score(
            self.planner.detect_goal_type("plan " + goal), new_val
        )

    def _background_goal_worker(self):
        while self.background_running:
            if self.goal_manager.active_goals:
                goal = self.goal_manager.active_goals[0]
                if self.dev_mode:
                    log_dev("planner", f"Background processing goal: {goal}")
                try:
                    step = None
                    with self.queue_lock:
                        if not self.tool_queue.empty():
                            priority, step = self.tool_queue.get(False)
                            self.queued_tasks.discard(step)
                    if step:
                        self.process(step, is_step=True)
                        self.task_tree.mark_task_complete(goal, step)
                except Exception as e:
                    logger.error(f"Background goal error: {e}")
            time.sleep(30)


# ============================================================
# CLI entry point
# ============================================================

def run_cli():
    agent = GcoreXAgent(speak_output=True)
    agent.print_startup_banner()

    if agent.goal_manager.active_goals:
        try:
            ans = input("Resume unfinished goals? (y/n): ").strip().lower()
            if ans == "y":
                for g in list(agent.goal_manager.active_goals):
                    agent.process(f"auto {g}")
        except (KeyboardInterrupt, EOFError):
            pass

    while True:
        try:
            user = input(Fore.WHITE + "\nYou: " + Style.RESET_ALL).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user:
            continue

        if user.lower() in ["exit", "quit", "bye"]:
            agent.speak("Goodbye.")
            break

        agent.process(user)


if __name__ == "__main__":
    run_cli()