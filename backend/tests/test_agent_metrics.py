import time

from agent.monitor import PerformanceMonitor


def test_metrics_measure_user_visible_ttft_and_counts():
    monitor = PerformanceMonitor()
    monitor.record_node_start("run-supervisor", "supervisor")
    monitor.record_llm_call("supervisor")
    time.sleep(0.002)
    monitor.record_node_end("run-supervisor", "supervisor")

    monitor.record_tool_start("run-rag", "search_knowledge_base", "research")
    monitor.record_llm_call("research")
    monitor.record_tool_end("run-rag")
    monitor.record_first_user_visible_token("research")

    monitor.record_llm_call("research")
    monitor.finish()
    metrics = monitor.get_metrics()

    assert metrics.ttft_ms > 0
    assert metrics.total_latency_ms >= metrics.ttft_ms
    assert metrics.node_time_ms["supervisor"] > 0
    assert metrics.llm_calls["supervisor"] == 1
    assert metrics.llm_calls["research"] == 2
    assert metrics.tool_calls["search_knowledge_base"] == 1
    assert metrics.tool_time_ms["search_knowledge_base"] > 0
    assert "TTFT:" in str(metrics)
    assert "FirstUserVisibleToken:" in str(metrics)
