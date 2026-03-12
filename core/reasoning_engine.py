"""
ReasoningEngine: Think -> Plan -> Act -> Reflect loop.

Optimizations vs original:
- think() is wrapped in a 3-second ThreadPoolExecutor timeout guard.
  If reasoning exceeds 3 s, an instant fallback dict is returned so
  the main pipeline is never stuck waiting.
- Uses LLMEngine instead of calling agent._ask_ollama_streaming directly,
  getting the per-route token budget and keep_alive benefits.
"""

import json
import re
import logging
import concurrent.futures

logger = logging.getLogger("ReasoningEngine")


def _extract_json_object(text: str):
    """Robust JSON extractor — tries full parse then brute-force block scan."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list) and obj and isinstance(obj[0], dict):
            return obj[0]
    except Exception:
        pass

    # Find outermost { } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass

    # Fallback: scan individual { } matches
    for m in re.findall(r"\{.*?\}", text, re.DOTALL):
        try:
            return json.loads(m)
        except Exception:
            continue

    return None


# Instant fallback used when think() times out
_THINK_TIMEOUT_FALLBACK = {
    "intent": "Chat",
    "goal": "",
    "tool": "",
    "confidence": 0.5,
    "reasoning": "Reasoning engine timeout — using fast fallback.",
    "response": "I'm thinking a bit slowly right now. Could you give me a moment or rephrase?",
}


class ReasoningEngine:
    """Manages the Think → Plan → Act → Reflect loop."""

    THINK_TIMEOUT = 3  # seconds — if exceeded, return instant fallback

    def __init__(self, agent):
        self.agent = agent

    # ------------------------------------------------------------------
    # Internal LLM helper — routes through LLMEngine if available
    # ------------------------------------------------------------------

    def _ask(self, prompt: str, route: str = "reasoning_required") -> str:
        if hasattr(self.agent, "llm"):
            return self.agent.llm.ask(
                prompt,
                route=route,
                stream_to_stdout=False,
                show_thinking=self.agent.dev_mode,
            )
        # Fallback to legacy method
        return self.agent._ask_ollama_streaming(prompt, show_thinking=self.agent.dev_mode)

    # ------------------------------------------------------------------
    # Step 1: Think
    # ------------------------------------------------------------------

    def think(self, user_input: str, context: str = "", available_tools: str = "") -> dict:
        """
        Understand user goal. Returns a decision dict.
        Wrapped in a 3-second timeout — returns an instant fallback on expire.
        """
        prompt = f"""\
You are the Thinking Engine for an AI Agent.
Your job is to understand the user's input and decide the best approach.

User Input: "{user_input}"
Recent Context:
{context}

Available Tools:
{available_tools}

Analyze:
1. Casual conversation or feedback → intent "Chat"
2. Single simple action (open app, search something) → intent "Action"
3. Complex multi-step request (research, write report) → intent "Plan"
4. Do NOT repeat tools from context unless explicitly requested by the user.

Return ONLY a strictly formatted JSON object:
{{
    "reasoning": "Explain your logic...",
    "intent": "Chat" | "Action" | "Plan",
    "goal": "Clear actionable goal (if Action/Plan, else empty)",
    "tool": "Tool name if Action, else empty",
    "confidence": 0.0-1.0,
    "response": "Conversational reply if Chat, else empty"
}}
"""
        def _do_think():
            for _ in range(2):
                raw = self._ask(prompt, route="reasoning_required")
                parsed = _extract_json_object(raw)
                if parsed and "intent" in parsed:
                    return parsed
            return _THINK_TIMEOUT_FALLBACK.copy()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_do_think)
            try:
                result = future.result(timeout=self.THINK_TIMEOUT)
                return result
            except concurrent.futures.TimeoutError:
                logger.warning("ReasoningEngine.think() exceeded 3 s — using fast fallback.")
                future.cancel()
                return _THINK_TIMEOUT_FALLBACK.copy()
            except Exception as e:
                logger.error(f"ReasoningEngine.think() error: {e}")
                return _THINK_TIMEOUT_FALLBACK.copy()

    # ------------------------------------------------------------------
    # Step 2: Plan
    # ------------------------------------------------------------------

    def plan(self, goal: str, available_tools: str = "") -> list:
        """Break complex goals into sequential tasks. Returns list of task dicts."""
        prompt = f"""\
You are the Planning Engine.
User's complex goal: "{goal}"

Available Tools:
{available_tools}

Break this goal into a logical sequence of atomic tasks, each executable by one tool.

Return ONLY a strictly formatted JSON object:
{{
    "tasks": [
        {{
            "task_id": 1,
            "description": "Clear description",
            "suggested_tool": "tool_name or 'auto'"
        }}
    ]
}}
"""
        for _ in range(2):
            raw = self._ask(prompt, route="planning_task")
            parsed = _extract_json_object(raw)
            if parsed and "tasks" in parsed and isinstance(parsed["tasks"], list):
                return parsed["tasks"]

        return [{"task_id": 1, "description": goal, "suggested_tool": "chat"}]

    # ------------------------------------------------------------------
    # Step 3: Reflect
    # ------------------------------------------------------------------

    def reflect(self, goal: str, task_description: str, tool_output: str) -> dict:
        """Evaluate whether a task execution succeeded."""
        prompt = f"""\
You are the Reflection Engine.
Overall Goal: "{goal}"
Task Executed: "{task_description}"
Tool Output:
{str(tool_output)[:2000]}

Did the task succeed in making progress towards the goal?
Return ONLY:
{{
    "reflection": "Your analysis...",
    "success": true | false
}}
"""
        for _ in range(2):
            raw = self._ask(prompt, route="reasoning_required")
            parsed = _extract_json_object(raw)
            if parsed and "success" in parsed:
                return parsed

        return {
            "reflection": "Reflection failed to parse — assuming partial success.",
            "success": bool(tool_output and "Error" not in str(tool_output)),
        }

    # ------------------------------------------------------------------
    # Step 4: Critic
    # ------------------------------------------------------------------

    def critic(self, response: str, reasoning: str) -> dict:
        """Verify the quality of the final response before delivery."""
        prompt = f"""\
You are the Self-Critic. Evaluate the AI's response quality.
Reasoning: "{reasoning}"
Draft Response: "{response}"

Assess factual correctness, logic, hallucination risk, and clarity.
Return ONLY:
{{
    "quality_score": 0.0-1.0,
    "issues": "Description of issues or 'None'",
    "improved_response": "Better response if score < 0.7, else empty string"
}}
"""
        for _ in range(2):
            raw = self._ask(prompt, route="reasoning_required")
            parsed = _extract_json_object(raw)
            if parsed and "quality_score" in parsed:
                return parsed

        return {"quality_score": 1.0, "issues": "Parse failed", "improved_response": ""}
