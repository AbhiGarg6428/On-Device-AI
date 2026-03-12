"""
ResponseValidator: Checks whether the LLM's response satisfies the user request.

Validation rules:
  - Word-count requests  ("N words")   → word count must be within 85–120% of N
  - Summary/summarize requests         → response must be < 100 words
  - List/bullet requests               → response must contain list markers
  - Completeness guard                 → response must be > 10 characters

Returns (is_valid, reason, correction_hint).
"""

import re
import logging

logger = logging.getLogger("ResponseValidator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(text.split())


def _extract_word_count_target(user_input: str):
    """
    Parse patterns like '100 words', '200-word', 'in 150 words' etc.
    Returns the integer target, or None.
    """
    patterns = [
        r'\b(\d{2,4})\s*[\-\s]?word',   # 100-word / 100 word
        r'\b(\d{2,4})\s+words?\b',       # 100 words / 100 word
        r'in\s+(\d{2,4})\s+words?\b',    # in 100 words
        r'at\s+least\s+(\d{2,4})\s+words?\b',  # at least 100 words
    ]
    text = user_input.lower()
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                val = int(m.group(1))
                if 10 <= val <= 5000:
                    return val
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------

class ResponseValidator:
    """
    Validates a generated response against the original user request.

    Usage::
        validator = ResponseValidator()
        is_valid, reason, hint = validator.validate(user_input, response)
    """

    # Tolerance band for word-count checks
    WORD_COUNT_LOW  = 0.85   # must deliver at least 85% of target
    WORD_COUNT_HIGH = 1.20   # anything up to 120% is fine

    def validate(self, user_input: str, response: str):
        """
        Returns:
            is_valid (bool)         – True if the response passes all checks
            reason   (str)          – Human-readable failure reason (empty if valid)
            hint     (str)          – Correction hint passed to the regeneration prompt
        """
        if not response or len(response.strip()) < 10:
            return False, "the response appears to be empty or incomplete", "the response is incomplete — provide a full answer"

        t = user_input.lower()
        wc = _word_count(response)

        # ── 1. Word-count check ───────────────────────────────────────────
        target = _extract_word_count_target(user_input)
        if target is not None:
            low  = int(target * self.WORD_COUNT_LOW)
            high = int(target * self.WORD_COUNT_HIGH)
            if wc < low:
                return (
                    False,
                    f"the response is too short ({wc} words) — the user asked for ~{target} words",
                    f"rewrite it to approximately {target} words (currently {wc}); expand with more detail, examples, and explanation",
                )
            if wc > high:
                return (
                    False,
                    f"the response is too long ({wc} words) — the user asked for ~{target} words",
                    f"shorten it to approximately {target} words (currently {wc}); keep only the most important points",
                )

        # ── 2. Summary brevity check ──────────────────────────────────────
        if re.search(r'\b(summarize|summary|brief|concise|short summary|in brief|tldr|tl;dr)\b', t):
            if wc > 120:
                return (
                    False,
                    f"the summary is too long ({wc} words) — summaries should be concise",
                    f"shorten the response to under 100 words while keeping the key points",
                )

        # ── 3. List / bullet-point check ─────────────────────────────────
        if re.search(r'\b(list|bullet|numbered list|steps|points)\b', t):
            has_list = bool(
                re.search(r'(\n\s*[-*•]|\n\s*\d+\.|\n\s*\d+\))', response)
            )
            if not has_list:
                return (
                    False,
                    "the response does not include a list format as the user requested",
                    "reformat the answer as a bulleted or numbered list",
                )

        # ── 4. Completeness guard ─────────────────────────────────────────
        if len(response.strip()) < 20:
            return (
                False,
                "the response is suspiciously short and may be incomplete",
                "provide a complete, well-formed answer",
            )

        return True, "", ""

    def get_word_count_target(self, user_input: str):
        """Public proxy to the helper, used by GcoreX to bump token budget."""
        return _extract_word_count_target(user_input)
