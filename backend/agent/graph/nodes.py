"""LangGraph 循环图节点 —— async（create_react_agent 实例缓存复用）

supervisor_node：规则高置信度路由优先 + LLM 兜底
_run_worker: 限制传参消息数量，只保留必要上下文
synthesize_node: 也使用 ReAct Agent 来支持真正的流式输出
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
    from tools.tool_manager import register_default_tools
    register_default_tools()
    from langgraph.prebuilt import create_react_agent
    llm = get_llm(streaming=True)
    _agent_cache["research"] = create_react_agent(llm, get_research_tools())
    _agent_cache["data"] = create_react_agent(llm, get_data_tools())
    _agent_cache["general"] = create_react_agent(llm, get_general_tools())
    _agent_cache["synthesizer"] = create_react_agent(llm, [])
    _agent_initialized = True
    logger.info(f"Agent 缓存就绪：research/data/general/synthesizer")


def _get_agent(agent_key: str):
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
    - 双阈值策略：第一名分数>=5 且与第二名分差>=2 → 直接使用规则路由
    - 低置信度或分差不够 → 调用 Supervisor LLM 决策
    """
    step = state.get("step_count", 0) + 1
    history: list[str] = list(state.get("route_history", []))
    last_worker = state.get("last_worker", "")
    
    user_text = _latest_user_text(state)
    
    # Step 1: 先尝试启发式规则路由
    rule_target, confidence = heuristic_route(user_text, history)
    
    # Step 2: 双阈值判断是否可以直接使用规则
    decision = None
    llm_call_used = False
    
    if confidence >= 5:
        scores = score_keywords_all(user_text, history)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_score = sorted_scores[0][1]
        second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0
        
        # 双阈值：best >= 5 AND (best - second) >= 2
        if best_score >= 5 and (best_score - second_score) >= 2:
            decision = rule_target
            logger.debug(f"[Heuristic High Confidence] route={decision}")
        else:
            logger.debug(f"[Heuristic Ambiguous] first={best_score}, second={second_score}, fallback to LLM")
            llm_call_used = True
    else:
        llm_call_used = True
    
    # Step 3: 如果 LLM 需要被调用
    if llm_call_used:
        context = build_supervisor_context(history, step)
        
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
        
        if decision is None:
            decision = rule_target
            logger.warning(f"[LLM Fallback] using heuristic: {decision}")
        
        logger.debug(f"[Supervisor LLM] route={decision}")
    
    # Step 4: 避免重复路由的安全策略
    if decision != "FINISH" and decision == last_worker:
        decision = "FINISH"
        logger.debug(f"[Safety Cycle] switching to FINISH")
    
    if decision == "FINISH" and not history:
        decision = rule_target
        logger.debug(f"[Safety First] first time but FINISH, using heuristic")
    
    # Step 5: 返回结果
    if decision != "FINISH":
        history = history + [decision]
    
    return {
        "next_agent": decision,
        "route_history": [decision] if decision != "FINISH" else [],
        "step_count": step,
    }


def score_keywords_all(text: str, route_history: list[str]) -> dict[str, int]:
    """计算所有候选 Agent 的关键词得分（用于双阈值判断）"""
    scores = {
        "research": score_keywords(text, RESEARCH_KEYWORDS),
        "data": score_keywords(text, DATA_KEYWORDS),
        "general": score_keywords(text, GENERAL_KEYWORDS),
    }
    
    for agent in route_history:
        if agent in scores:
            scores[agent] = max(0, scores[agent] - 2)
    
    return scores


async def _run_worker(state: AgentState, agent_key: RouteTarget) -> dict:
    """Worker 执行，仅传入必要的上下文消息"""
    agent = _get_agent(agent_key)
    worker_messages = _prepare_worker_messages(state, agent_key)
    
    logger.debug(f"[Worker {agent_key}] messages: {len(worker_messages)}")
    
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


def _prepare_worker_messages(state: AgentState, agent_key: RouteTarget) -> list:
    """准备 Worker 所需的消息列表，限制上下文长度"""
    messages = state.get("messages", [])
    result = [SystemMessage(content=WORKER_PROMPTS[agent_key])]
    
    latest_user_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg
            break
    
    if latest_user_msg:
        result.append(latest_user_msg)
    
    worker_msg_count = 0
    for msg in reversed(messages):
        if worker_msg_count >= 3:
            break
        if hasattr(msg, 'additional_kwargs'):
            agent = msg.additional_kwargs.get('agent', '')
            if agent in ('research', 'data', 'general'):
                result.append(msg)
                worker_msg_count += 1
    
    return result


async def research_node(state: AgentState) -> dict:
    return await _run_worker(state, "research")


async def data_node(state: AgentState) -> dict:
    return await _run_worker(state, "data")


async def general_node(state: AgentState) -> dict:
    return await _run_worker(state, "general")


async def synthesize_node(state: AgentState) -> dict:
    """聚合多个 Worker 结果，生成最终回答"""
    synthesizer_messages = [
        SystemMessage(content=SYNTHESIS_PROMPT),
        *state["messages"][-12:],
    ]
    
    agent = _get_agent("synthesizer")
    result = await agent.ainvoke({"messages": synthesizer_messages})
    
    last_msg = result["messages"][-1]
    if isinstance(last_msg, AIMessage):
        tagged = AIMessage(
            content=last_msg.content,
            additional_kwargs={"agent": "synthesizer", "agent_label": "最终回答"},
        )
        return {"messages": [tagged]}
    
    return {"messages": [AIMessage(content=str(last_msg.content))]}
