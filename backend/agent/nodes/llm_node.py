"""
LLM Node —— 调用大模型生成回答
"""
from agent.state.agent_state import AgentState
from services.llm_service import call_llm

def build_prompt(state: AgentState) -> str:
    """根据 state 构建 LLM 提示词"""
    question = state["question"]
    context = state.get("retrieved_docs") or state.get("tool_result") or ""
    if context:
        return f"你是一个企业助手。根据以下参考信息回答用户问题。\n\n参考信息：{context}\n\n用户问题：{question}"
    else:
        return f"你是一个企业助手。请直接回答用户问题。\n\n用户问题：{question}"


def llm_node(state: AgentState) -> AgentState:
    """根据检索结果或工具生成最终回答"""
    prompt = build_prompt(state)
    answer = call_llm("你是一个专业的企业 AI 助手，请用中文回答。", prompt)
    state["final_answer"] = answer
    return state