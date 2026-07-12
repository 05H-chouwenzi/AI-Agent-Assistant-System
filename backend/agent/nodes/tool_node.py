"""
Tool Node —— 外部工具调用节点（完整实现）

架构:
    Planner (预选工具 + 参数)
        ↓
    Tool Node
        ├── 1. 从 state["tool_calls"] 读取预选结果
        ├── 2. 如果没有预选 → ToolRouter 即时路由
        ├── 3. ToolManager 执行工具
        └── 4. 结果写回 state
        ↓
    LLM Node (用 tool_result 生成回答)
"""
import json
from agent.state.agent_state import AgentState
from tools.tool_manager import get_tool_manager
from tools.tool_router import ToolRouter
from logs.logger import logger

# 全局 ToolRouter 实例
_router = ToolRouter()


def tool_node(state: AgentState) -> AgentState:
    """
    执行工具调用节点

    流程:
    1. 检查 state["tool_calls"] — planner 可能已预选工具
    2. 如果预选存在 → 直接执行
    3. 如果预选不存在 → 用 ToolRouter 即时决定（规则优先，LLM 兜底）
    4. 执行成功 → 结果写入 state["tool_result"] + state["tool_results"]
    5. 执行失败 → 降级为 LLM 直接回答
    """
    question = state["question"]
    history = state.get("history", [])
    preselected = state.get("tool_calls")

    manager = get_tool_manager()

    if manager.is_empty():
        logger.warning("Tool Node: 没有注册任何工具")
        state["tool_result"] = "工具系统暂未就绪，请稍后再试。"
        return state

    # ========== 1. 检查预选 ==========
    tool_name = None
    tool_args = {}

    if preselected and len(preselected) > 0:
        first = preselected[0]
        tool_name = first.get("tool_name")
        tool_args = first.get("arguments", {})
        logger.info(f"Tool Node: 使用 Planner 预选 → [{tool_name}]")

    # ========== 2. 没有预选 → 仅关键词规则匹配（零 LLM）==========
    if not tool_name:
        tool_schemas = manager.get_function_schemas()
        # ★ 仅关键词规则匹配，跳过 LLM 路由（LLM 调用交由外层处理）
        # 关键词规则匹配（零 LLM 调用，~1ms）
        tool_name, tool_args = _router._keyword_route(question, tool_schemas)
        if tool_name:
            logger.info(f"Tool Node: 关键词规则命中 → [{tool_name}], 参数: {tool_args}")
        else:
            # 关键词未命中 → 尝试关键词兜底
            tool_name, tool_args, reason = _router._keyword_fallback(question, tool_schemas)
            if tool_name:
                logger.info(f"Tool Node: 关键词兜底命中 → [{tool_name}] (原因: {reason})")

        if not tool_name:
            logger.info("Tool Node: 规则未匹配到工具，降级为外层 LLM 处理")
            state["tool_result"] = ""
            return state

    # ========== 3. 注入用户上下文 + 执行工具 ==========
    # 自动注入 user_id，工具自行决定是否使用
    user_id = state.get("user_id")
    if user_id is not None:
        tool_args.setdefault("user_id", user_id)

    result = manager.execute(tool_name, **tool_args)

    # ========== 4. 写回状态 ==========
    # 记录到结构化字段
    call_record = {
        "tool_name": tool_name,
        "arguments": tool_args,
        "result": result.to_dict(),
        "success": result.success,
        "error": result.error,
        "execution_time_ms": result.execution_time_ms,
    }
    state["tool_calls"] = [call_record]
    state["tool_results"] = [result.to_dict()]

    # 兼容旧格式
    state["tool_result"] = result.to_message()

    return state
