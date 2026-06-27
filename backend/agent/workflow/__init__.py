"""
Workflow 构建器 —— 用 LangGraph 组装 Agent 工作流
"""
from langgraph.graph import StateGraph,END
from agent.state.agent_state import AgentState
from agent.nodes import planner_node, llm_node, response_node, rag_node, tool_node

"""
Workflow 构建器 —— 用 LangGraph 组装 Agent 工作流
"""
def build_workflow():
    """构建 Agent 工作流图"""
    workflow=StateGraph(AgentState)

    # 注册所有节点
    workflow.add_node("planner",planner_node)
    workflow.add_node("rag",rag_node)
    workflow.add_node("tool",tool_node)
    workflow.add_node("llm",llm_node)
    workflow.add_node("response",response_node)
    # 入口
    workflow.set_entry_point("planner")

    # 条件路由：根据任务类型分发
    workflow.add_conditional_edges(
        "planner",
        lambda state:state["task_type"],
        {
            "rag":"rag",
            "tool":"tool",
            "direct":"llm",
        }
    )
    # RAG / Tool 执行完 → 进 LLM 生成回答
    workflow.add_edge("rag","llm")
    workflow.add_edge("tool","llm")

    # 所有路径最终汇聚到 response
    workflow.add_edge("llm","response")
    workflow.add_edge("response",END)
    
    return workflow.compile()
    