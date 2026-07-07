"""
LLM Node —— 调用大模型生成回答（支持结构化工具结果）
"""
from agent.state.agent_state import AgentState
from services.llm_service import call_llm


def build_prompt(state: AgentState) -> str:
    """根据 state 构建 LLM 提示词（不含历史，历史单独传）

    优先使用结构化 tool_results，其次是旧工具结果/检索文档
    """
    question = state["question"]

    # 新格式：结构化工具结果
    tool_results = state.get("tool_results")
    if tool_results and len(tool_results) > 0:
        import json
        context_parts = []
        for tr in tool_results:
            data = tr.get("data", {})
            if isinstance(data, (dict, list)):
                context_parts.append(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                context_parts.append(str(data))
        context = "\n\n".join(context_parts)
        return (
            "你是一个企业助手。根据以下工具查询结果回答用户问题。\n\n"
            f"工具结果：\n{context}\n\n"
            f"用户问题：{question}"
        )

    # 旧格式兼容
    context = state.get("retrieved_docs") or state.get("tool_result") or ""
    if context:
        if isinstance(context, list):
            context = "\n".join(str(c) for c in context)
        return f"你是一个企业助手。根据以下参考信息回答用户问题。\n\n参考信息：{context}\n\n用户问题：{question}"
    else:
        return f"你是一个企业助手。请直接回答用户问题。\n\n用户问题：{question}"


def prompt_builder_node(state: AgentState) -> AgentState:
    """构建 LLM 提示词并写入 state['prompt']，不调用 LLM API

    专为 LangGraph Workflow 设计，让图只负责数据流，
    LLM 调用（含流式）交由 API 层处理。
    """
    state["prompt"] = build_prompt(state)
    return state