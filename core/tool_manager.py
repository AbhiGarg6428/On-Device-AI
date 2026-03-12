"""
GcoreXToolManager: Dynamic plugin loader and executor.
Extracted from GcoreX.py with one key addition:
  execute_background() runs tools in daemon threads so they never block
  the main response pipeline.
"""

import os
import sys
import time
import logging
import traceback
import importlib
import pkgutil
import concurrent.futures
import threading

logger = logging.getLogger("ToolManager")


class GcoreXToolManager:
    """Manages dynamic loading and execution of plugin tools."""

    def __init__(self, tools_dir: str = "tools"):
        self.tools_dir = tools_dir
        self.tools: dict = {}
        self.modules: dict = {}
        self.last_executed: dict = {}
        self.tool_health: dict = {}
        self._load_plugins()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_plugins(self):
        self.tools = {"chat": "Use this for normal conversation and answering general questions"}
        self.modules = {}

        base_path = os.path.dirname(os.path.dirname(__file__))  # project root
        tools_path = os.path.join(base_path, self.tools_dir)

        if not os.path.exists(tools_path):
            logger.warning(f"Tools directory '{tools_path}' not found.")
            return

        if base_path not in sys.path:
            sys.path.append(base_path)

        loaded_count = 0
        invalid_count = 0
        print(f"\nScanning for tools in '{self.tools_dir}/'...")

        for _, module_name, _ in pkgutil.iter_modules([tools_path]):
            try:
                full_module_name = f"{self.tools_dir}.{module_name}"
                if full_module_name in sys.modules:
                    importlib.reload(sys.modules[full_module_name])

                module = importlib.import_module(full_module_name)
                if hasattr(module, "name") and hasattr(module, "description") and hasattr(module, "run"):
                    self.tools[module.name] = module.description
                    self.modules[module.name] = module
                    self.tool_health[module.name] = {"success": 0, "fail": 0}
                    print(f"  [✓] Loaded: {module.name}")
                    loaded_count += 1
                else:
                    logger.warning(f"Tool '{module_name}' missing required attributes (name/description/run).")
                    print(f"  [X] Invalid: {module_name}")
                    invalid_count += 1
            except Exception as e:
                logger.error(f"Failed to load plugin {module_name}: {e}")
                print(f"  [!] Error: {module_name} ({e})")
                invalid_count += 1

        print(f"Finished loading {loaded_count} tools ({invalid_count} failed).\n")

    # ------------------------------------------------------------------
    # Descriptions
    # ------------------------------------------------------------------

    def get_descriptions(self) -> str:
        return "\n".join([f'- "{k}": {v}' for k, v in self.tools.items()])

    def get_tool_success_rate(self, tool_name: str) -> float:
        stats = self.tool_health.get(tool_name)
        if not stats:
            return 1.0
        total = stats["success"] + stats["fail"]
        return stats["success"] / total if total > 0 else 1.0

    def get_tool_health_report(self) -> str:
        report = ["Tool Name | Success | Failure | Rate %", "-" * 50]
        for name, stats in self.tool_health.items():
            s, f = stats["success"], stats["fail"]
            rate = (s / (s + f) * 100) if (s + f) > 0 else 0.0
            report.append(f"{name:12} | {s:7} | {f:7} | {rate:.2f}%")
        return "\n".join(report)

    # ------------------------------------------------------------------
    # Execution — blocking
    # ------------------------------------------------------------------

    def execute(self, action: str, value: str, timeout: int = 15):
        if action == "chat":
            return None
        if action == "speak":
            return None

        if action not in self.modules:
            return f"Tool '{action}' not found."

        # Cooldown (2 s)
        now = time.time()
        if action in self.last_executed and (now - self.last_executed[action]) < 2.0:
            logger.warning(f"Cooldown active: '{action}' blocked.")
            return f"Tool '{action}' is on cooldown. Wait a moment."
        self.last_executed[action] = now

        if action not in self.tool_health:
            self.tool_health[action] = {"success": 0, "fail": 0}

        # Auto-disable after 5 consecutive failures
        if self.tool_health[action]["fail"] >= 5:
            self.modules.pop(action, None)
            logger.warning(f"Tool '{action}' auto-disabled after 5 failures.")
            return f"Tool '{action}' was auto-disabled due to repeated failures."

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(self.modules[action].run, value)
                result = future.result(timeout=timeout)
                self.tool_health[action]["success"] += 1
                return result
        except concurrent.futures.TimeoutError:
            self.tool_health[action]["fail"] += 1
            logger.error(f"Tool '{action}' timed out after {timeout}s.")
            return f"Tool '{action}' took too long and was stopped."
        except Exception as e:
            self.tool_health[action]["fail"] += 1
            logger.error(f"Tool '{action}' error: {e}")
            logger.debug(traceback.format_exc())
            return f"Tool '{action}' failed: {e}"

    # ------------------------------------------------------------------
    # Execution — non-blocking background thread
    # ------------------------------------------------------------------

    def execute_background(self, action: str, value: str, timeout: int = 15) -> concurrent.futures.Future:
        """
        Run a tool in a daemon thread. Returns a Future immediately so the
        caller can optionally await the result without blocking the main thread.

        Usage:
            future = tool_manager.execute_background("search", "python tips")
            # ... continue responding to user ...
            result = future.result(timeout=15)  # optional wait
        """
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.execute, action, value, timeout)

        # Shutdown executor once future completes (daemon thread, no blocking)
        def _cleanup(f):
            executor.shutdown(wait=False)

        future.add_done_callback(_cleanup)
        return future
