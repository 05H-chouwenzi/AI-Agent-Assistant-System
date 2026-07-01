"""
LangGraph Workflow —— 企业 AI 智能助手工作流图

图结构:
    START → planner_node
               │ (conditional: task_type)
          ┌────┼────┐
          │    │    │
          ▼    ▼    ▼
        rag   tool  (direct → prompt_builder)
          │    │
          └────┘
             │
             ▼
       prompt_builder_node → END

LLM 调用（含流式）在图外由 API 层处理，保持图节点为纯数据流。
"""
from langgraph.graph import StateGraph, START, END
from agent.state.agent_state import AgentState
from agent.nodes.planner import planner_node
from agent.nodes.rag_node import rag_node
from agent.nodes.tool_node import tool_node
from agent.nodes.llm_node import prompt_builder_node


def route_after_planner(state: AgentState) -> str:
    """根据 task_type 路由到下一个节点

    Returns:
        "rag" → RAG 知识库检索
        "tool" → 工具调用
        "direct" → 直接到 prompt_builder
    """
    return state.get("task_type", "direct")


def _build_graph():
    """构建并编译完整的 Agent 工作流图"""
    graph = StateGraph(AgentState)

    # ── 节点 ──
    graph.add_node("planner", planner_node)
    graph.add_node("rag", rag_node)
    graph.add_node("tool", tool_node)
    graph.add_node("prompt_builder", prompt_builder_node)

    # ── 边 ──
    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "rag": "rag",
            "tool": "tool",
            "direct": "prompt_builder",
        },
    )
    graph.add_edge("rag", "prompt_builder")
    graph.add_edge("tool", "prompt_builder")
    graph.add_edge("prompt_builder", END)

    return graph.compile()


# 全局单例 —— 模块导入时自动构建
agent_graph = _build_graph()
