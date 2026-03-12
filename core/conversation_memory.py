"""
ConversationMemory: Sliding window for smart context-aware chat.
"""

import json
import os
import logging

logger = logging.getLogger("ConversationMemory")

class ConversationMemory:
    """Manages a sliding window of recent messages for context-aware chat."""

    def __init__(self, file_path="conv_history.json", max_messages=8):
        self.file_path = file_path
        self.max_messages = max_messages
        self.history = []
        self.load()

    def load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load conversation memory: {e}")
                self.history = []
        self._trim()

    def save(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save conversation memory: {e}")

    def _trim(self):
        """Keep only the last max_messages."""
        if len(self.history) > self.max_messages:
            self.history = self.history[-self.max_messages:]

    def add_message(self, role, content):
        """Adds a message to history and saves to disk."""
        if content:
            self.history.append({"role": role, "content": content})
            self._trim()
            self.save()

    def get_recent_context(self):
        """Returns the list of recent messages."""
        return self.history

    def clear(self):
        """Resets the conversation history."""
        self.history = []
        self.save()
