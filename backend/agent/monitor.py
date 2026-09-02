"""Agent Performance Monitor"""
import time
from dataclasses import dataclass, field
from typing import List
from logs.logger import logger

@dataclass
class AgentMetrics:
    supervisor_llm_calls: int = 0
    research_llm_calls: int = 0
    data_llm_calls: int = 0
    general_llm_calls: int = 0
    synthesize_llm_calls: int = 0
    rag_search_calls: int = 0
    mysql_calls: int = 0
    weather_calls: int = 0
    http_calls: int = 0
    total_steps: int = 0
    ttft_ms: int = 0
    total_latency_ms: int = 0
    route_history: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "llm_calls": {
                "supervisor": self.supervisor_llm_calls,
                "research": self.research_llm_calls,
                "data": self.data_llm_calls,
                "general": self.general_llm_calls,
                "synthesize": self.synthesize_llm_calls,
                "total": sum([self.supervisor_llm_calls, self.research_llm_calls, self.data_llm_calls, self.general_llm_calls, self.synthesize_llm_calls]),
            },
            "tool_calls": {
                "rag_search": self.rag_search_calls,
                "mysql": self.mysql_calls,
                "weather": self.weather_calls,
                "http": self.http_calls,
                "total": sum([self.rag_search_calls, self.mysql_calls, self.weather_calls, self.http_calls]),
            },
            "steps": self.total_steps,
            "ttft_ms": self.ttft_ms,
            "total_latency_ms": self.total_latency_ms,
            "route_history": self.route_history,
        }

    def __str__(self):
        total_llm = sum([self.supervisor_llm_calls, self.research_llm_calls, self.data_llm_calls, self.general_llm_calls, self.synthesize_llm_calls])
        total_tool = sum([self.rag_search_calls, self.mysql_calls, self.weather_calls, self.http_calls])
        routes = " ".join(self.route_history) if self.route_history else "N/A"
        lines = [
            "=== Agent Performance Metrics ===",
            "LLM Calls:",
            f"  Supervisor = {self.supervisor_llm_calls}",
            f"  Research = {self.research_llm_calls}",
            f"  Data = {self.data_llm_calls}",
            f"  General = {self.general_llm_calls}",
            f"  Synthesize = {self.synthesize_llm_calls}",
            f"  Total = {total_llm}",
            "",
            "Tool Calls:",
            f"  RAG Search = {self.rag_search_calls}",
            f"  MySQL = {self.mysql_calls}",
            f"  Weather = {self.weather_calls}",
            f"  HTTP = {self.http_calls}",
            f"  Total = {total_tool}",
            "",
            f"Agent Steps: {self.total_steps}",
            "",
            "Time Metrics:",
            f"  TTFT: {self.ttft_ms} ms",
            f"  Total: {self.total_latency_ms} ms",
            "",
            f"Route History: {routes}",
        ]
        return "\n".join(lines)


class PerformanceMonitor:
    def __init__(self):
        self.metrics = AgentMetrics()
        self.start_time = None

    def start(self):
        self.start_time = time.time()
        self.metrics = AgentMetrics()

    def record_ttft(self, elapsed_ms):
        self.metrics.ttft_ms = elapsed_ms

    def record_supervisor_call(self):
        self.metrics.supervisor_llm_calls += 1

    def record_worker_call(self, worker_type):
        if worker_type == "research":
            self.metrics.research_llm_calls += 1
        elif worker_type == "data":
            self.metrics.data_llm_calls += 1
        elif worker_type == "general":
            self.metrics.general_llm_calls += 1

    def record_synthesize_call(self):
        self.metrics.synthesize_llm_calls += 1

    def record_tool_call(self, tool_name):
        if "rag" in tool_name.lower() or "search" in tool_name.lower():
            self.metrics.rag_search_calls += 1
        elif "mysql" in tool_name.lower() or "sql" in tool_name.lower():
            self.metrics.mysql_calls += 1
        elif "weather" in tool_name.lower():
            self.metrics.weather_calls += 1
        else:
            self.metrics.http_calls += 1

    def record_step(self):
        self.metrics.total_steps += 1

    def record_route(self, route):
        if route and route not in self.metrics.route_history:
            self.metrics.route_history.append(route)

    def stop(self, total_elapsed_ms):
        self.metrics.total_latency_ms = total_elapsed_ms

    def get_metrics(self):
        return self.metrics

    def print_metrics(self):
        logger.info(str(self.get_metrics()))
