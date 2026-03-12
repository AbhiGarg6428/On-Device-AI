"""
MemoryManager: Combines short-term chat history and semantic vector memory.
Extracted from GcoreX.py — wraps GcoreXMemory and GcoreXVectorMemory.
"""

import os
import json
import math
import re
import logging
import threading

logger = logging.getLogger("MemoryManager")


class GcoreXMemory:
    """Handles conversation history with safe atomic writes."""

    def __init__(self, file_path: str = "memory.json", max_history: int = 20):
        self.file_path = file_path
        self.max_history = max_history
        self.history = []
        self.load()

    def load(self):
        if not os.path.exists(self.file_path):
            self._trim()
            return
        try:
            if os.path.getsize(self.file_path) > 1024 * 1024:
                logger.warning("Memory file > 1 MB — recreating.")
                self.history = []
                self.save()
                return

            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.history = data.get("chat_history", [])
        except json.JSONDecodeError:
            logger.warning("Memory file corrupted — recreating.")
            self.history = []
            self.save()
        except Exception as e:
            logger.error(f"Memory Load Error: {e}")
            self.history = []
        self._trim()

    def save(self):
        self._trim()
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"chat_history": self.history}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception as e:
            logger.error(f"Memory Save Error: {e}")

    def _trim(self):
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def add_interaction(self, user_text: str, ai_text: str):
        try:
            if user_text or ai_text:
                self.history.append({"user": user_text, "gcorex": ai_text})
                self._trim()
                self.save()
        except Exception as e:
            logger.error(f"Memory append error: {e}")

    def get_context_string(self, limit: int = 5) -> str:
        recent = self.history[-limit:]
        return "\n".join(
            [f"User: {m.get('user', '')}\nGcoreX: {m.get('gcorex', '')}" for m in recent]
        )


class GcoreXVectorMemory:
    """Semantic vector memory using TF-IDF cosine similarity (+ Ollama embeddings when available)."""

    MAX_KNOWLEDGE = 2000

    def __init__(self, file_path: str = "knowledge.json"):
        self.file_path = file_path
        self.knowledge = []
        self.knowledge_text_index: set = set()
        self.cache: dict = {}
        self.embedding_cache: dict = {}
        self.embedding_cache_lock = threading.Lock()
        self.knowledge_lock = threading.Lock()
        self.load()

    def load(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.knowledge = json.load(f).get("entries", [])
                self.knowledge_text_index = {k.get("text", "").strip() for k in self.knowledge}
        except Exception as e:
            logger.error(f"Vector Memory Load Error: {e}")

    def save(self):
        try:
            tmp = f"{self.file_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"entries": self.knowledge}, f, indent=2)
            os.replace(tmp, self.file_path)
        except Exception as e:
            logger.error(f"Vector Memory Save Error: {e}")

    # ------------------------------------------------------------------
    # Embedding / similarity helpers
    # ------------------------------------------------------------------

    def _tf_idf(self, text: str) -> dict:
        words = re.findall(r"\w+", text.lower())
        tf: dict = {}
        for w in words:
            tf[w] = tf.get(w, 0) + 1
        return tf

    def _cosine_dict(self, d1: dict, d2: dict) -> float:
        common = set(d1) & set(d2)
        num = sum(d1[x] * d2[x] for x in common)
        denom = math.sqrt(sum(v ** 2 for v in d1.values())) * math.sqrt(sum(v ** 2 for v in d2.values()))
        return float(num) / denom if denom else 0.0

    def _cosine_list(self, v1: list, v2: list) -> float:
        if not v1 or not v2:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a ** 2 for a in v1))
        n2 = math.sqrt(sum(b ** 2 for b in v2))
        return float(dot) / (n1 * n2) if n1 * n2 else 0.0

    def get_embedding(self, text: str):
        with self.embedding_cache_lock:
            if text in self.embedding_cache:
                return self.embedding_cache[text]
        try:
            import requests
            res = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
                timeout=2,
            )
            if res.status_code == 200:
                emb = res.json().get("embedding")
                if emb:
                    with self.embedding_cache_lock:
                        self.embedding_cache[text] = emb
                        if len(self.embedding_cache) > 500:
                            self.embedding_cache.pop(next(iter(self.embedding_cache)))
                return emb
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_knowledge(self, text: str):
        if not text.strip():
            return
        if len(text) > 1500:
            text = text[:1500]

        vec = self._tf_idf(text)
        emb = self.get_embedding(text)
        entry = {"text": text, "vector": vec}
        if emb:
            entry["embedding"] = emb

        with self.knowledge_lock:
            self.knowledge.append(entry)
            self.knowledge_text_index.add(text.strip())
            if len(self.knowledge) > self.MAX_KNOWLEDGE:
                self.knowledge = self.knowledge[-int(self.MAX_KNOWLEDGE * 0.8):]
                self.knowledge_text_index = {k.get("text", "").strip() for k in self.knowledge}
            self.cache.clear()

        self.save()

    def forget_knowledge(self, text: str) -> bool:
        with self.knowledge_lock:
            before = len(self.knowledge)
            self.knowledge = [k for k in self.knowledge if text.lower() not in k["text"].lower()]
            if len(self.knowledge) < before:
                self.knowledge_text_index = {k.get("text", "").strip() for k in self.knowledge}
                self.save()
                return True
        return False

    def search_knowledge(self, query: str, top_k: int = 3) -> list:
        if not self.knowledge:
            return []
        if query in self.cache:
            return self.cache[query]

        q_emb = self.get_embedding(query)
        q_vec = self._tf_idf(query)
        scored = []
        for k in self.knowledge:
            if q_emb and "embedding" in k:
                score = self._cosine_list(q_emb, k["embedding"])
            else:
                score = self._cosine_dict(q_vec, k.get("vector", {}))
            if score > 0.1:
                scored.append((score, k["text"]))

        scored.sort(reverse=True, key=lambda x: x[0])
        results = [item[1] for item in scored[:top_k]]

        self.cache[query] = results
        if len(self.cache) > 200:
            self.cache.pop(next(iter(self.cache)))
        return results
