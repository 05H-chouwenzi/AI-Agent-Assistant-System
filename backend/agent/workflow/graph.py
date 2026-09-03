"""LangGraph Workflow —— 直线图（Worker 完成后直接结束）

  START -> supervisor（路由）
            ├── research / data / general（create_react_agent）
            │       └── END
"""
from agent.graph.nodes import (
    data_node,
    general_node,
    research_node,
    supervisor_node,
)
from agent.graph.router import (
    route_from_supervisor,
)
from agent.graph.state import AgentState


def _build_graph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("research", research_node)
    graph.add_node("data", data_node)
    graph.add_node("general", general_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "research": "research",
            "data": "data",
            "general": "general",
            "end": END,
        },
    )

    # Worker 完成后直接结束（不再循环回 supervisor）
    for worker in ("research", "data", "general"):
        graph.add_edge(worker, END)

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
