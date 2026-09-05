"""LangGraph Workflow —— 循环图（Worker 回到 Supervisor；多 Worker 结果聚合）

  START -> supervisor（路由）
            ├── research / data / general（create_react_agent）
            │       └── supervisor
            └── FINISH → 1 个 Worker：END / ≥2 个 Worker：synthesize
"""
from agent.graph.nodes import (
    data_node,
    general_node,
    research_node,
    supervisor_node,
    synthesize_node,
)
from agent.graph.router import (
    route_from_supervisor,
)
from agent.graph.state import AgentState


_WORKER_NODES = {"research", "data", "general"}


def _route_after_supervisor(state: AgentState) -> str:
    """FINISH 后根据已参与的不同 Worker 数量决定是否聚合。"""
    next_target = route_from_supervisor(state)
    if next_target != "end":
        return next_target

    distinct_workers = set(state.get("route_history") or []) & _WORKER_NODES
    return "synthesize" if len(distinct_workers) >= 2 else "end"

def _build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("research", research_node)
    graph.add_node("data", data_node)
    graph.add_node("general", general_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_after_supervisor,
        {
            "research": "research",
            "data": "data",
            "general": "general",
            "synthesize": "synthesize",
            "end": END,
        },
    )

    # Worker 完成后回到 Supervisor（循环入口；是否结束由 Supervisor 的 next_agent 决定）
    for worker in ("research", "data", "general"):
        graph.add_edge(worker, "supervisor")

    graph.add_edge("synthesize", END)

    return graph.compile()


_agent_graph = None


def get_agent_graph():
    """懒加载 agent_graph（首次调用时才编译，避免导入时延迟）"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = _build_graph()
    return _agent_graph


# 向后兼容：保留 agent_graph 属性访问
class _GraphProxy:
    """代理对象，首次访问任意属性时才触发真正的图编译"""
    def __getattr__(self, name):
        return getattr(get_agent_graph(), name)


agent_graph = _GraphProxy()
