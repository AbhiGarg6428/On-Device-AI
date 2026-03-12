import json
import os
import logging

logger = logging.getLogger(__name__)

class Memory:
    def __init__(self, filepath="memory.json", max_history=20):
        self.filepath = filepath
        self.max_history = max_history
        self.chat_history = []
        self.load()

    def load(self):
        """Loads conversation history from disk."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chat_history = data.get("chat_history", [])
            except Exception as e:
                logger.error(f"Error loading memory: {e}")
                self.chat_history = []
        else:
            self.chat_history = []
        self._trim()

    def save(self):
        """Saves current conversation state to disk."""
        self._trim()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"chat_history": self.chat_history}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving memory: {e}")

    def _trim(self):
        """Automatically trims history to the max limit."""
        if len(self.chat_history) > self.max_history:
            self.chat_history = self.chat_history[-self.max_history:]

    def add_user_message(self, text):
        self.chat_history.append({"role": "user", "content": text})
        self.save()

    def add_ai_message(self, text):
        self.chat_history.append({"role": "assistant", "content": text})
        self.save()

    def get_context(self, limit=5):
        """Returns the recent conversational context as a string."""
        context = []
        # Return only a smaller window for prompt size limits
        for msg in self.chat_history[-limit:]:
            context.append(f"{msg['role'].capitalize()}: {msg['content']}")
        return "\n".join(context)
