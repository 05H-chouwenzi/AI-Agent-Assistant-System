"""Per-request Agent performance monitor."""
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from logs.logger import logger


NODE_NAMES = ("fast_router", "supervisor", "research", "data", "general", "synthesize")
LLM_NAMES = ("supervisor", "research", "data", "general", "synthesize")

@dataclass
class AgentMetrics:
    request_start_epoch_ms: int = 0
    request_start_perf_ns: int = 0
    first_user_visible_token_epoch_ms: Optional[int] = None
    first_user_visible_token_perf_ns: Optional[int] = None
    first_token_source: str = ""
    total_latency_ms: float = 0.0
    node_time_ms: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    llm_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    llm_time_ms: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    llm_durations_ms: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    tool_calls: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tool_time_ms: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    route_history: List[str] = field(default_factory=list)

    @property
    def ttft_ms(self) -> float:
        if self.first_user_visible_token_perf_ns is None:
            return 0.0
        return (self.first_user_visible_token_perf_ns - self.request_start_perf_ns) / 1_000_000

    def to_dict(self):
        first_token_time = self.first_user_visible_token_epoch_ms
        return {
            "request_start": self.request_start_epoch_ms,
            "first_user_visible_token": first_token_time,
            "ttft_ms": self.ttft_ms,
            "total_latency_ms": self.total_latency_ms,
            "first_token_source": self.first_token_source,
            "node_time_ms": dict(self.node_time_ms),
            "llm_calls": {
                **{name: self.llm_calls.get(name, 0) for name in LLM_NAMES},
                "total": sum(self.llm_calls.values()),
            },
            "llm_time_ms": dict(self.llm_time_ms),
            "llm_durations_ms": {
                name: list(durations) for name, durations in self.llm_durations_ms.items()
            },
            "tool_calls": {
                **dict(self.tool_calls),
                "total": sum(self.tool_calls.values()),
            },
            "tool_time_ms": dict(self.tool_time_ms),
            "route_history": self.route_history,
        }

    def __str__(self):
        routes = " -> ".join(self.route_history) if self.route_history else "N/A"
        tool_lines = [
            f"  {name}: {count} ({self.tool_time_ms.get(name, 0):.0f}ms)"
            for name, count in self.tool_calls.items()
        ]
        lines = [
            "[AgentMetrics]",
            f"RequestStart: {datetime.fromtimestamp(self.request_start_epoch_ms / 1000)}",
            f"FirstUserVisibleToken: {datetime.fromtimestamp(self.first_user_visible_token_epoch_ms / 1000) if self.first_user_visible_token_epoch_ms else 'N/A'}",
            f"TTFT: {self.ttft_ms:.0f}ms",
            f"Total: {self.total_latency_ms:.0f}ms",
            f"FirstTokenSource: {self.first_token_source or 'N/A'}",
            "",
            "Node Time:",
            *[f"  {name}: {self.node_time_ms.get(name, 0):.0f}ms" for name in NODE_NAMES],
            "",
            "LLM:",
            *self._llm_log_lines(),
            "",
            "Tool Calls:",
            *(tool_lines or ["  N/A"]),
            "",
            f"Route History: {routes}",
        ]
        return "\n".join(lines)

    def _llm_log_lines(self):
        lines = []
        llm_names = [*LLM_NAMES, *(name for name in self.llm_calls if name not in LLM_NAMES)]
        for name in llm_names:
            calls = self.llm_calls.get(name, 0)
            if not calls:
                continue
            total_ms = self.llm_time_ms.get(name, 0)
            duration_text = f", {total_ms:.0f}ms" if self.llm_durations_ms.get(name) else ""
            call_text = "call" if calls == 1 else "calls"
            lines.append(f"  {name}: {calls} {call_text}{duration_text}")
            for index, elapsed_ms in enumerate(self.llm_durations_ms.get(name, []), 1):
                lines.append(f"    {name}_llm_{index}: {elapsed_ms:.0f}ms")
        if not lines:
            lines.append("  N/A")
        return lines


class PerformanceMonitor:
    def __init__(self):
        self.metrics = AgentMetrics()
        self.metrics.request_start_perf_ns = time.perf_counter_ns()
        self.metrics.request_start_epoch_ms = time.time_ns() // 1_000_000
        self._node_starts: Dict[str, tuple[str, int]] = {}
        self._run_nodes: Dict[str, str] = {}
        self._tool_starts: Dict[str, tuple[str, int]] = {}
        self._llm_starts: Dict[str, tuple[str, int]] = {}

    def record_first_user_visible_token(self, source: str) -> None:
        if self.metrics.first_user_visible_token_perf_ns is not None:
            return
        now_ns = time.perf_counter_ns()
        self.metrics.first_user_visible_token_perf_ns = now_ns
        self.metrics.first_user_visible_token_epoch_ms = time.time_ns() // 1_000_000
        self.metrics.first_token_source = source

    def record_node_start(self, run_id: str, node: str) -> None:
        if node in NODE_NAMES:
            self._node_starts[run_id] = (node, time.perf_counter_ns())
            self._run_nodes[run_id] = node

    def resolve_node(self, node: str, parent_ids) -> str:
        """Resolve a nested subgraph event back to its outer workflow node."""
        if node in NODE_NAMES:
            return node
        if isinstance(parent_ids, list):
            for run_id in reversed(parent_ids):
                if run_id in self._run_nodes:
                    return self._run_nodes[run_id]
        return ""

    def record_node_end(self, run_id: str, node: str) -> None:
        started = self._node_starts.pop(run_id, None)
        if not started:
            return
        actual_node, started_ns = started
        self.metrics.node_time_ms[actual_node] += (
            time.perf_counter_ns() - started_ns
        ) / 1_000_000

    def record_llm_call(self, node: str) -> None:
        self.metrics.llm_calls[node if node in LLM_NAMES else "unknown"] += 1

    def record_llm_start(self, run_id: str, node: str) -> None:
        llm_name = node if node in LLM_NAMES else "unknown"
        self.metrics.llm_calls[llm_name] += 1
        self._llm_starts[run_id] = (llm_name, time.perf_counter_ns())

    def record_llm_end(self, run_id: str) -> None:
        started = self._llm_starts.pop(run_id, None)
        if not started:
            return
        llm_name, started_ns = started
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        self.metrics.llm_time_ms[llm_name] += elapsed_ms
        self.metrics.llm_durations_ms[llm_name].append(elapsed_ms)

    def record_tool_start(self, run_id: str, tool_name: str, node: str = "") -> None:
        del node
        self.metrics.tool_calls[tool_name] += 1
        self._tool_starts[run_id] = (tool_name, time.perf_counter_ns())

    def record_tool_end(self, run_id: str) -> None:
        started = self._tool_starts.pop(run_id, None)
        if not started:
            return
        tool_name, started_ns = started
        self.metrics.tool_time_ms[tool_name] += (
            time.perf_counter_ns() - started_ns
        ) / 1_000_000

    def record_tool_duration(self, tool_name: str, elapsed_ms: float) -> None:
        self.metrics.tool_calls[tool_name] += 1
        self.metrics.tool_time_ms[tool_name] += elapsed_ms

    def record_route(self, route: str) -> None:
        if route and route not in self.metrics.route_history:
            self.metrics.route_history.append(route)

    def finish(self) -> None:
        if not self.metrics.total_latency_ms:
            self.metrics.total_latency_ms = (
                time.perf_counter_ns() - self.metrics.request_start_perf_ns
            ) / 1_000_000

    def get_metrics(self):
        return self.metrics

    def print_metrics(self):
        logger.info(str(self.get_metrics()))
