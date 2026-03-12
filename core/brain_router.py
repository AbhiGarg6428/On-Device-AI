"""
BrainRouter: Classifies user inputs into 4 route types to direct
them through the correct processing pipeline — avoiding the expensive
reasoning engine for simple queries.

Routes:
  fast_chat          — greetings, acks, very short chitchat
  tool_command       — explicit action prefixes (open/search/play/calc/run)
  reasoning_required — complex analysis, explanation, deep questions
  planning_task      — multi-step goals, system building, research projects
"""

import re


# ---------------------------------------------------------------------------
# Classification data
# ---------------------------------------------------------------------------

# Prefixes that always mean a tool should run directly
TOOL_PREFIXES = (
    "open ", "launch ", "start ",
    "search ", "google ", "find ", "lookup ",
    "play ", "watch ", "listen ",
    "calculate ", "calc ", "compute ",
    "run ", "execute ",
    "read ", "summarize ",
    "/",
)

REASONING_KEYWORDS = [
    "analyze", "analyse",
    "explain", "how does", "how do", "how can", "how should",
    "what is the difference", "what is",
    "why ", "why is", "why does",
    "compare", "pros and cons", "advantages", "disadvantages",
    "deep dive", "in depth", "in detail", "elaborate", "tell me about",
    "describe", "define", "what are",
]

PLANNING_KEYWORDS = [
    "plan ", "strategy", "build a", "create system", "create a system",
    "step by step", "step-by-step", "architecture", "roadmap",
    "write a report", "write a guide",
    "develop", "outline", "design a",
]

CONVERSATIONAL_EXACT = {
    "hi", "hey", "hello", "yo", "sup",
    "ok", "okay", "k", "sure",
    "good", "great", "nice", "cool", "awesome", "wow",
    "thanks", "thank you", "thx", "ty",
    "yes", "no", "nope", "yep", "yeah",
    "bye", "goodbye", "see you",
    "got it", "makes sense",
}


class BrainRouter:
    """Routes user input to the appropriate processing pipeline."""

    def classify(self, text: str) -> str:
        """
        Returns one of:
          'fast_chat'          — skip LLM reasoning, quick response
          'tool_command'       — direct tool execution
          'reasoning_required' — engage reasoning engine
          'planning_task'      — engage planner + reasoning engine
        """
        if not text:
            return "fast_chat"

        t = text.lower().strip()
        t_clean = re.sub(r"[^\w\s]", "", t).strip()
        words = t_clean.split()

        # 1. Exact conversational matches → fast_chat (fastest check)
        if t_clean in CONVERSATIONAL_EXACT:
            return "fast_chat"

        # 2. Explicit tool prefix → tool_command
        #    Must run BEFORE the short-text check so 'open chrome', 'play X' etc.
        #    are not mis-classified as fast_chat due to low word count.
        for prefix in TOOL_PREFIXES:
            if t.startswith(prefix):
                return "tool_command"

        # 3. Math expression → tool_command (calculator)
        if re.search(r"\d+\s*[\+\-\*/\^]\s*\d+", t):
            return "tool_command"

        # 4. Very short text (≤ 3 words, ≤ 20 chars) → fast_chat
        if len(t) <= 20 and len(words) <= 3:
            return "fast_chat"

        # 5. Planning keywords → planning_task (before reasoning)
        if any(kw in t for kw in PLANNING_KEYWORDS):
            return "planning_task"

        # 6. Reasoning keywords → reasoning_required
        if any(kw in t for kw in REASONING_KEYWORDS):
            return "reasoning_required"

        # 7. Long open-ended queries (> 10 words) → reasoning_required
        if len(words) > 10:
            return "reasoning_required"

        # Default: fast chat with LLM
        return "fast_chat"