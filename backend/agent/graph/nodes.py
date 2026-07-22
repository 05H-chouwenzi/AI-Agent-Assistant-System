"""LangGraph 循环图节点 —— async（create_react_agent 实例缓存复用）

supervisor_node：LLM 路由 + 启发式兜底（关键词优先）
_run_worker：create_react_agent 执行，Agent 实例全局缓存
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
    from langgraph.prebuilt import create_react_agent
    llm = get_llm(streaming=True)
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

    # 安全阀：步数或重复路由过多 → 直接 FINISH
    if should_finish(step, history, last_worker or None):
        return {"next_agent": "FINISH", "step_count": step}

    user_text = _latest_user_text(state)
    context = build_supervisor_context(history, step)

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
        decision = heuristic_route(user_text, history)

    # Worker 已执行且 LLM 再次指向同一 Agent → 改为 FINISH，避免死循环
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


async def synthesize_node(state: AgentState) -> dict:
    """聚合多个 Worker 结果，生成最终回答"""
    llm = get_llm(streaming=True)
    response = await llm.ainvoke(
        [SystemMessage(content=SYNTHESIS_PROMPT), *state["messages"][-12:]]
    )
    if isinstance(response, AIMessage):
        tagged = AIMessage(
            content=response.content,
            additional_kwargs={"agent": "synthesizer", "agent_label": "最终回答"},
        )
        return {"messages": [tagged]}
    return {"messages": [AIMessage(content=str(response.content))]}
