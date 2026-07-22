"""LangGraph Workflow —— 循环图（Worker 完成后回 supervisor 继续调度，多步Agent协作）

  START -> supervisor（LLM路由 + 启发式兜底）
             ┦┬ research / data / general（create_react_agent）
             ┦       └ supervisor / synthesize
             ┦└┬┬┬ synthesize → END
"""
from agent.graph.nodes import (
    data_node,
    general_node,
    research_node,
    supervisor_node,
    synthesize_node,
)
from agent.graph.router import (
    route_after_worker,
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
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "research": "research",
            "data": "data",
            "general": "general",
            "synthesize": "synthesize",
            "end": END,
        },
    )

    for worker in ("research", "data", "general"):
        graph.add_conditional_edges(
            worker,
            route_after_worker,
            {"supervisor": "supervisor", "synthesize": "synthesize"},
        )

    graph.add_edge("synthesize", END)

    return graph.compile()


_agent_graph = None


def get_agent_graph():
    """懒加载 agent_graph（首次调用时才编译，避免导入时延迟）"""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = _build_graph()
    return _agent_graph


class _GraphProxy:
    def __getattr__(self, name):
        return getattr(get_agent_graph(), name)


agent_graph = _GraphProxy()
