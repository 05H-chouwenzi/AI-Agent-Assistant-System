"""LangGraph 循环图节点 —— async（create_react_agent 实例缓存复用）

supervisor_node：规则高置信度路由优先 + LLM 兜底
_run_worker：限制传参消息数量，只保留必要上下文
synthesize_node：也使用 ReAct Agent 来支持真正的流式输出
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.graph.router import (
    build_supervisor_context,
    AGENT_LABELS,
    MAX_GRAPH_STEPS,
    SUPERVISOR_PROMPT,
    SYNTHESIS_PROMPT,
    WORKER_PROMPTS,
    heuristic_route,
    parse_supervisor_decision,
    should_finish,
    RouteTarget,
    score_keywords,
    RESEARCH_KEYWORDS,
    DATA_KEYWORDS,
    GENERAL_KEYWORDS,
)
from agent.graph.state import AgentState
from agent.llm import get_llm
from tools.langchain_tools import get_research_tools, get_data_tools, get_general_tools
from logs.logger import logger


# ====== 全局缓存 create_react_agent 实例 ======
_agent_cache: dict[str, object] = {}
_agent_initialized = False


def _build_agents():
    """初始化并缓存所有 Agent 实例"""
    global _agent_initialized, _agent_cache
    if _agent_initialized:
        return
    # 确保工具已注册：否则 create_react_agent 会绑定空工具列表，
    # 导致 Worker 无法调用工具、输出空回答
    from tools.tool_manager import register_default_tools
    register_default_tools()
    from langgraph.prebuilt import create_react_agent
    llm = get_llm(streaming=True)
    _agent_cache["research"] = create_react_agent(llm, get_research_tools())
    _agent_cache["data"] = create_react_agent(llm, get_data_tools())
    _agent_cache["general"] = create_react_agent(llm, get_general_tools())
    _agent_cache["synthesizer"] = create_react_agent(llm, [])  # Synthesizer 不需要工具
    _agent_initialized = True
    logger.info(f"Agent 缓存就绪：research/data/general/synthesizer")


def _get_agent(agent_key: str) -> object:
    """获取缓存的 Agent 实例"""
    _build_agents()
    return _agent_cache[agent_key]


def _latest_user_text(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


async def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 节点：规则高置信度路由优先 + LLM 兜底
    
    优化方案：
    - 高置信度（评分≥5） → 直接使用规则路由，跳过 LLM 调用
    - 低置信度（评分<5） → 调用 Supervisor LLM 决策
    """
    step = state.get("step_count", 0) + 1
    history: list[str] = list(state.get("route_history", []))
    last_worker = state.get("last_worker", "")
    
    user_text = _latest_user_text(state)
    
    # ====== Step 1: 先尝试启发式规则路由 ======
    rule_target, confidence = heuristic_route(user_text, history)
    
    # ====== Step 2: 高置信度直接走规则，低置信度回退 LLM ======
    decision = None
    llm_call_used = False
    
    if confidence >= 5:  # HIGH_CONFIDENCE_THRESHOLD
        # 高置信度：直接使用规则路由，不调用 LLM
        decision = rule_target
        logger.debug(f"[Heuristic High Confidence] route={decision}, confidence={confidence}, text=\"{user_text[:50]}...\"")
    else:
        # 低置信度：调用 Supervisor LLM 兜底
        context = build_supervisor_context(history, step)
        
        # 安全阀检查
        if should_finish(step, history, last_worker or None):
            return {"next_agent": "FINISH", "step_count": step}
        
        llm = get_llm(streaming=False)
        response = await llm.ainvoke(
            [
                SystemMessage(content=SUPERVISOR_PROMPT),
                SystemMessage(content=context),
                *state["messages"][-8:],
            ]
        )
        raw = response.content if isinstance(response.content, str) else str(response.content)
        decision = parse_supervisor_decision(raw)
        llm_call_used = True
        
        # LLM 决策为空时回退到启发式
        if decision is None:
            decision = rule_target
            logger.warning(f"[LLM Fallback to Heuristic] LLM returned empty, using heuristic: {decision}")
        
        logger.debug(f"[Supervisor LLM] route={decision}, was_llm_call=true, text=\"{user_text[:50]}...\"")
    
    # ====== Step 3: 避免重复路由的安全策略 ======
    
    # Worker 已执行且 LLM/规则再次指向同一 Agent → 改为 FINISH，避免死循环
    if decision != "FINISH" and decision == last_worker:
        decision = "FINISH"
        logger.debug(f"[Safety Avoid Cycle] same worker twice, switching to FINISH")
    
    # 首次路由：若决策是 FINISH 但尚未执行任何 Worker，用启发式修正
    if decision == "FINISH" and not history:
        decision = rule_target
        logger.debug(f"[Safety First Route] first time but FINISH, using heuristic instead")
    
    # ====== Step 4: 返回结果 ======
    if decision != "FINISH":
        history = history + [decision]
    
    return {
        "next_agent": decision,
        "route_history": [decision] if decision != "FINISH" else [],
        "step_count": step,
    }


def _prepare_worker_messages(state: AgentState, agent_key: RouteTarget) -> list:
    """
    准备 Worker 所需的消息列表，限制上下文长度
    
    策略：
    1. System Prompt（必选）
    2. 当前用户最新问题（必选）
    3. 最近的 Worker 回复（最多保留 3 条，用于上下文衔接）
    4. 不传入大量历史聊天消息
    """
    messages = state.get("messages", [])
    
    # Step 1: System Prompt
    result = [SystemMessage(content=WORKER_PROMPTS[agent_key])]
    
    # Step 2: 查找当前用户最新问题
    latest_user_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg
            break
    
    if latest_user_msg:
        result.append(latest_user_msg)
    
    # Step 3: 查找最近的 Worker 回复（用于上下文衔接）
    worker_msg_count = 0
    worker_msgs_needed = 3  # 最多保留 3 条 Worker 回复作为上下文
    
    for msg in reversed(messages):
        if worker_msg_count >= worker_msgs_needed:
            break
        
        if hasattr(msg, 'additional_kwargs'):
            agent = msg.additional_kwargs.get('agent', '')
            if agent in ('research', 'data', 'general'):
                result.append(msg)
                worker_msg_count += 1
    
    return result


async def _run_worker(state: AgentState, agent_key: RouteTarget) -> dict:
    """Worker 执行，仅传入必要的上下文消息"""
    agent = _get_agent(agent_key)
    
    # 准备有限的上下文消息
    worker_messages = _prepare_worker_messages(state, agent_key)
    
    logger.debug(
        f"[Worker {agent_key}] 消息数量：{len(worker_messages)}, "
        f"总状态消息数：{len(state.get('messages', []))}"
    )
    
    result = await agent.ainvoke({"messages": worker_messages})
    
    last_msg = result["messages"][-1]
    label = AGENT_LABELS.get(agent_key, agent_key)
    if isinstance(last_msg, AIMessage):
        tagged = AIMessage(
            content=last_msg.content,
            additional_kwargs={**last_msg.additional_kwargs, "agent": agent_key, "agent_label": label},
        )
        return {"messages": [tagged], "last_worker": agent_key}
    return {"messages": [last_msg], "last_worker": agent_key}


async def research_node(state: AgentState) -> dict:
    return await _run_worker(state, "research")


async def data_node(state: AgentState) -> dict:
    return await _run_worker(state, "data")


async def general_node(state: AgentState) -> dict:
    return await _run_worker(state, "general")


async def synthesize_node(state: AgentState) -> dict:
    """聚合多个 Worker 结果，生成最终回答
    
    关键：使用 ReAct Agent 来实现真正的流式输出！
    """
    # 准备 Synthesizer 需要的消息（只需要系统提示 + 历史消息）
    synthesizer_messages = [
        SystemMessage(content=SYNTHESIS_PROMPT),
        *state["messages"][-12:],
    ]
    
    # 使用缓存的 synthesizer agent（已经配置了 streaming=True 的 LLM）
    agent = _get_agent("synthesizer")
    
    # 调用 ReAct Agent（会触发 stream 事件）
    result = await agent.ainvoke({"messages": synthesizer_messages})
    
    # 处理返回的消息
    last_msg = result["messages"][-1]
    
    if isinstance(last_msg, AIMessage):
        tagged = AIMessage(
            content=last_msg.content,
            additional_kwargs={"agent": "synthesizer", "agent_label": "最终回答"},
        )
        return {"messages": [tagged]}
    
    return {"messages": [AIMessage(content=str(last_msg.content))]}
