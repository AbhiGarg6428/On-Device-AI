"""
LLMEngine: Optimized Ollama wrapper for GcoreX.

Key optimizations:
- keep_alive: "10m" keeps model loaded between calls (avoids reload cost)
- Per-route token budgets prevent over-generating on simple queries
- Real token-by-token streaming to sys.stdout
- Fast fallback on connection/timeout errors
"""

import json
import logging
import sys
import threading

logger = logging.getLogger("LLMEngine")

# Token budgets by route type
TOKEN_BUDGET = {
    "fast_chat":          250,
    "tool_command":       80,
    "reasoning_required": 350,
    "planning_task":      400,
    "self_correction":    600,   # generous budget for correction regeneration
    "default":            120,
}

# Shared import lock for lazy loading requests
_requests_lock = threading.Lock()
_requests = None


def _get_requests():
    global _requests
    if _requests is None:
        with _requests_lock:
            if _requests is None:
                import requests as req
                _requests = req
    return _requests


class LLMEngine:
    """
    Thread-safe Ollama LLM wrapper with streaming, keep_alive,
    and per-route token budgets.
    """

    def __init__(
        self,
        model: str = "mistral",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.host = host
        self.generate_url = f"{host}/api/generate"
        self.chat_url = f"{host}/api/chat"

    def ask(
        self,
        prompt: str,
        route: str = "default",
        stream_to_stdout: bool = False,
        retries: int = 2,
        timeout: int = 30,
        show_thinking: bool = False,
        num_predict_override: int = 0,
        label: str = "",
        token_callback: callable = None,
    ) -> str:
        """Uses /api/generate for single prompt completion."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "10m"
        }
        return self._request(self.generate_url, payload, route, stream_to_stdout, retries, timeout, show_thinking, num_predict_override, label, token_callback=token_callback)

    def chat(
        self,
        messages: list,
        route: str = "default",
        stream_to_stdout: bool = False,
        retries: int = 2,
        timeout: int = 30,
        show_thinking: bool = False,
        num_predict_override: int = 0,
        label: str = "",
        token_callback: callable = None,
    ) -> str:
        """Uses /api/chat for multi-turn conversation."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": "10m"
        }
        return self._request(self.chat_url, payload, route, stream_to_stdout, retries, timeout, show_thinking, num_predict_override, label, is_chat=True, token_callback=token_callback)

    def _request(
        self,
        url: str,
        payload: dict,
        route: str,
        stream_to_stdout: bool,
        retries: int,
        timeout: int,
        show_thinking: bool,
        num_predict_override: int,
        label: str,
        is_chat: bool = False,
        token_callback: callable = None,
    ) -> str:
        num_predict = num_predict_override if num_predict_override > 0 else TOKEN_BUDGET.get(route, TOKEN_BUDGET["default"])
        payload["options"] = {
            "temperature": 0.7,
            "num_predict": num_predict,
            "top_k": 40,
        }
        req = _get_requests()

        for attempt in range(retries):
            try:
                with req.post(
                    url,
                    json=payload,
                    stream=True,
                    timeout=(5, timeout),
                ) as res:
                    res.raise_for_status()
                    full_text = ""

                    if show_thinking:
                        print("\nGcoreX thinking...")

                    if stream_to_stdout and label:
                        sys.stdout.write(label)
                        sys.stdout.flush()

                    try:
                        for line in res.iter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line.decode("utf-8", errors="ignore"))
                                if is_chat:
                                    token = chunk.get("message", {}).get("content", "")
                                else:
                                    token = chunk.get("response", "")
                                if token:
                                    full_text += token

                                    if token_callback:
                                        token_callback(token)

                                    if stream_to_stdout:
                                        sys.stdout.write(token)
                                        sys.stdout.flush()

                                if len(full_text) > 8000:
                                    full_text = full_text[: 8000]
                                    break

                            except json.JSONDecodeError:
                                continue
                    except Exception as stream_err:
                        logger.error(f"Stream interrupted: {stream_err}")
                    finally:
                        try:
                            res.close()
                        except Exception:
                            pass

                    # Only print trailing newline when something was written to stdout
                    if show_thinking or stream_to_stdout:
                        print("")

                    return full_text

            except Exception as exc:
                req_module = _get_requests()
                if isinstance(exc, req_module.exceptions.Timeout):
                    logger.warning(f"Ollama timeout (attempt {attempt + 1}/{retries})")
                    if attempt == retries - 1:
                        print("")
                        return '[{"action":"chat","response":"My reasoning timed out. Please try again."}]'
                elif isinstance(exc, req_module.exceptions.ConnectionError):
                    logger.error("Cannot connect to Ollama — is it running?")
                    print("")
                    return '[{"action":"chat","response":"Ollama is offline. Start Ollama and retry."}]'
                else:
                    logger.error(f"LLM error: {exc}")
                    if attempt == retries - 1:
                        print("")
                        return '[{"action":"chat","response":"LLM error — please retry."}]'

        return '[{"action":"chat","response":"Failed after retries."}]'

    def generate_full_response(self, prompt, route="default", **kwargs) -> str:
        """Helper for internal reasoning/validation where full text is needed first."""
        kwargs["stream_to_stdout"] = False
        return self.ask(prompt, route=route, **kwargs)

    def stream_response(self, prompt, route="fast_chat", label="", **kwargs) -> str:
        """Helper for user-facing chat where token-by-token output is desired."""
        kwargs["stream_to_stdout"] = True
        kwargs["label"] = label
        return self.ask(prompt, route=route, **kwargs)

    def ping(self) -> bool:
        """Returns True if Ollama is reachable."""
        try:
            req = _get_requests()
            res = req.get("http://localhost:11434/", timeout=2)
            return res.status_code == 200
        except Exception:
            return False
