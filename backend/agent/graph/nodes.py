"""LangGraph 循环图节点 —— async（create_react_agent 实例缓存复用）

supervisor_node：LLM 路由 + 启发式兜底（关键词优先）
_run_worker：create_react_agent 执行，Agent 实例全局缓存
"""
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.graph.router import (
    AGENT_LABELS,
    MAX_GRAPH_STEPS,
    SUPERVISOR_PROMPT,
    WORKER_PROMPTS,
    build_supervisor_context,
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
# 工具列表在启动时注册（register_default_tools），之后不再变化。
# 缓存 Agent 避免每次请求重复编译 ReAct Prompt。
_agent_cache: dict[str, object] = {}
_agent_initialized = False


def _build_agents():
    """初始化并缓存所有 Agent 实例（启动时或首次调用时执行一次）"""
    global _agent_initialized, _agent_cache

    if _agent_initialized:
        return

    from langgraph.prebuilt import create_react_agent

    llm = get_llm(streaming=True)  # 流式 LLM → SSE 逐 token 推送

    _agent_cache["research"] = create_react_agent(llm, get_research_tools())
    _agent_cache["data"] = create_react_agent(llm, get_data_tools())
    _agent_cache["general"] = create_react_agent(llm, get_general_tools())
    _agent_initialized = True

    logger.info(f"Agent 缓存就绪: research/data/general")


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
    step = state.get("step_count", 0) + 1
    history: list[str] = list(state.get("route_history", []))
    last_worker = state.get("last_worker", "")

    # 安全阀：步数或重复路由过多 → FINISH
    if should_finish(step, history, last_worker or None):
        return {"next_agent": "FINISH", "step_count": step}

    user_text = _latest_user_text(state)

    # ===== 第2+次调用：Worker 已执行 → 直接 FINISH（省一次 LLM 路由） =====
    if last_worker:
        logger.debug(f"Supervisor(step={step}) last_worker={last_worker} → FINISH (skip LLM)")
        return {"next_agent": "FINISH", "step_count": step}

    # ===== 首次路由：启发式匹配，不调 LLM（省 3-5s）=====
    heuristic = heuristic_route(user_text, history)
    scores = {
        "research": score_keywords(user_text, RESEARCH_KEYWORDS),
        "data": score_keywords(user_text, DATA_KEYWORDS),
        "general": score_keywords(user_text, GENERAL_KEYWORDS),
    }
    sorted_scores = sorted(scores.values(), reverse=True)
    best_score = sorted_scores[0] if sorted_scores else 0
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0

    # 得分明确 → 走启发式；不明确 → 默认 general（不调 LLM）
    if best_score >= 2 and (best_score - second_score) >= 2:
        decision = heuristic
        logger.debug(f"Supervisor(step={step}) heuristic={heuristic} scores={scores} → skip LLM")
    else:
        decision = "general"
        logger.debug(f"Supervisor(step={step}) heuristic={heuristic} scores={scores} → default to general")

    # Worker 已执行且 LLM 再次指向同一 Agent → 改为 FINISH
    if decision != "FINISH" and decision == last_worker:
        decision = "FINISH"

    # 首次路由：若 LLM 说 FINISH 但尚未执行任何 Worker，走启发式
    if decision == "FINISH" and not history:
        decision = heuristic_route(user_text, history)

    if decision != "FINISH":
        history = history + [decision]

    return {
        "next_agent": decision,
        "route_history": [decision] if decision != "FINISH" else [],
        "step_count": step,
    }


async def _run_worker(state: AgentState, agent_key: RouteTarget) -> dict:
    """执行 Worker（使用缓存的 create_react_agent，避免每次编译）"""
    agent = _get_agent(agent_key)
    result = await agent.ainvoke(
        {"messages": [SystemMessage(content=WORKER_PROMPTS[agent_key]), *state["messages"]]}
    )
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
