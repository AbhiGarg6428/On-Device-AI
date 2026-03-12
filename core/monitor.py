"""
GcoreXMonitor: Tracks latency, tool execution counts and health.
Extracted from GcoreX.py for modular architecture.
"""


class GcoreXMonitor:
    """Tracks latency, tools, and processing load."""

    def __init__(self):
        self.total_requests = 0
        self.latencies = []
        self.tool_executions = 0
        self.failed_tool_executions = 0
        self.tool_latencies = []

    def log_latency(self, sec: float):
        self.total_requests += 1
        self.latencies.append(sec)
        if len(self.latencies) > 1000:
            self.latencies = self.latencies[-1000:]

    def log_tool(self, sec: float, failed: bool = False):
        self.tool_executions += 1
        if failed:
            self.failed_tool_executions += 1
        self.tool_latencies.append(sec)
        if len(self.tool_latencies) > 1000:
            self.tool_latencies = self.tool_latencies[-1000:]

    def display(self, memory_size: int, loaded_tools_count: int, model: str, conn_status: str):
        avg = sum(self.latencies) / len(self.latencies) if self.latencies else 0.0
        avg_tool = sum(self.tool_latencies) / len(self.tool_latencies) if self.tool_latencies else 0.0
        print("\n" + "=" * 50)
        print("  GcoreX System Monitor [DEV MODE]")
        print("=" * 50)
        print(f"[*] Model         : {model}")
        print(f"[*] Connection    : {conn_status}")
        print(f"[*] Processed Reqs: {self.total_requests}")
        print(f"[*] Avg Latency   : {avg:.2f} seconds")
        print(f"[*] Tool Execs    : {self.tool_executions} run ({self.failed_tool_executions} failed)")
        print(f"[*] Avg Tool Time : {avg_tool:.2f} seconds")
        print(f"[*] Active Plugins: {loaded_tools_count}")
        print(f"[*] Memory Usage  : {memory_size} interactions")
        print("=" * 50 + "\n")
