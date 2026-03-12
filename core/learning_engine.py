"""
LearningEngine: Persists common mistake/correction pairs to learning_memory.json.

Each record:
{
    "trigger":     "100 words",
    "action":      "increase generation length",
    "occurrences": 3,
    "last_seen":   "2026-03-11T19:08:48"
}

The engine loads at startup and auto-saves after every update.
"""

import os
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger("LearningEngine")

# Default seed rules baked in — immediately useful even before any corrections occur
_DEFAULT_RULES = [
    {"trigger": "100 words",  "action": "increase generation length",  "occurrences": 0, "last_seen": ""},
    {"trigger": "200 words",  "action": "increase generation length",  "occurrences": 0, "last_seen": ""},
    {"trigger": "500 words",  "action": "increase generation length",  "occurrences": 0, "last_seen": ""},
    {"trigger": "summarize",  "action": "shorten the response",        "occurrences": 0, "last_seen": ""},
    {"trigger": "summary",    "action": "shorten the response",        "occurrences": 0, "last_seen": ""},
    {"trigger": "list",       "action": "format as a bulleted list",   "occurrences": 0, "last_seen": ""},
    {"trigger": "bullet",     "action": "format as a bulleted list",   "occurrences": 0, "last_seen": ""},
]


class LearningEngine:
    """
    Stores and retrieves correction rules from `learning_memory.json`.

    Usage::
        engine = LearningEngine()
        engine.record_correction("100 words", "increase generation length")
        hint = engine.get_hint("write me a 100 words essay")
    """

    def __init__(self, file_path: str = "learning_memory.json"):
        self.file_path = file_path
        self._lock = threading.Lock()
        self.rules: list = []
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        """Load from disk; if missing, seed with defaults."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Support both {"rules": [...]} and plain list format
                    if isinstance(data, list):
                        self.rules = data
                    elif isinstance(data, dict):
                        self.rules = data.get("rules", data.get("learning_rules", []))
                    else:
                        self.rules = []
                logger.debug(f"LearningEngine: loaded {len(self.rules)} rules from {self.file_path}")
                return
            except Exception as e:
                logger.error(f"LearningEngine load error: {e}")

        # First run — seed the file
        self.rules = [dict(r) for r in _DEFAULT_RULES]
        self._save()

    def _save(self):
        """Atomically write rules to disk."""
        try:
            tmp = self.file_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"rules": self.rules}, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.file_path)
        except Exception as e:
            logger.error(f"LearningEngine save error: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_correction(self, trigger: str, action: str):
        """
        Upsert a trigger/action pair. Increments `occurrences` and updates
        `last_seen`.  Saves automatically.
        """
        trigger = trigger.strip().lower()
        action  = action.strip().lower()
        if not trigger or not action:
            return

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        with self._lock:
            for rule in self.rules:
                if rule.get("trigger", "").lower() == trigger:
                    rule["action"]      = action
                    rule["occurrences"] = rule.get("occurrences", 0) + 1
                    rule["last_seen"]   = now
                    self._save()
                    logger.debug(f"LearningEngine: updated rule '{trigger}' (occurrences={rule['occurrences']})")
                    return

            # New rule
            self.rules.append({
                "trigger":     trigger,
                "action":      action,
                "occurrences": 1,
                "last_seen":   now,
            })
            self._save()
            logger.debug(f"LearningEngine: new rule added '{trigger}'")

    def get_hint(self, user_input: str) -> str:
        """
        Return the most relevant stored action for user_input (substring match).
        Returns empty string if nothing found.
        """
        text = user_input.lower()
        best: dict = {}
        best_count = -1

        with self._lock:
            for rule in self.rules:
                trigger = rule.get("trigger", "").lower()
                if trigger and trigger in text:
                    count = rule.get("occurrences", 0)
                    if count > best_count:
                        best = rule
                        best_count = count

        return best.get("action", "")

    def get_all(self) -> list:
        """Return a copy of all stored rules."""
        with self._lock:
            return list(self.rules)

    def summary_str(self) -> str:
        """Human-readable summary for dev/monitor output."""
        with self._lock:
            lines = [f"  • '{r['trigger']}' → '{r['action']}' (×{r.get('occurrences',0)})"
                     for r in self.rules]
        return "\n".join(lines) if lines else "  (no rules yet)"
