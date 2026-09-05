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
_WORKER_INPUT_MESSAGE_LIMIT = 8

SYNTHESIZE_PROMPT = """你是企业 AI Agent 平台的 Synthesize Node。

请基于多个 Agent 已经返回的真实执行结果，整合生成一条面向用户的最终回答。
要求：
1. 保留与用户问题相关的关键信息、数据和结论。
2. 去除重复内容和无关内容。
3. 不要虚构 Agent 结果中没有的信息。
4. 如果不同 Agent 结果存在冲突，明确说明差异，不要强行拼接。
"""


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


def warm_up_agents() -> None:
    """启动阶段预编译 Worker Agent，避免首次请求支付编译耗时。"""
    _build_agents()


def _latest_user_text(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _message_text(message: object) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _extract_worker_results(state: AgentState) -> list[tuple[str, str]]:
    """提取 Worker 最终消息；来源由 _run_worker 写入 additional_kwargs.agent。"""
    results: list[tuple[str, str]] = []
    for message in state.get("messages", []):
        if not isinstance(message, AIMessage):
            continue
        agent_key = message.additional_kwargs.get("agent")
        if agent_key not in AGENT_LABELS:
            continue
        content = _message_text(message).strip()
        if content:
            results.append((agent_key, content))
    return results


async def supervisor_node(state: AgentState) -> dict:
    step = state.get("step_count", 0) + 1
    history: list[str] = list(state.get("route_history", []))
    last_worker = state.get("last_worker", "")

    # 安全阀：步数或重复路由过多 → FINISH
    if should_finish(step, history, last_worker or None):
        return {"next_agent": "FINISH", "step_count": step}

    user_text = _latest_user_text(state)

    # Worker 完成后重新路由；已有 Worker 在 heuristic_route 中降权，避免无意义重复。
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

    # Worker 后若另一个未执行 Worker 的意图仍然明确，允许第二次调度。
    if last_worker:
        executed = set(history)
        adjusted_scores = {
            agent: max(0, score - 2) if agent in executed else score
            for agent, score in scores.items()
        }
        alternate_candidates = [
            (agent, score)
            for agent, score in adjusted_scores.items()
            if agent not in executed and score >= 2
        ]
        if alternate_candidates:
            alternate_agent, alternate_score = max(alternate_candidates, key=lambda item: item[1])
            current_score = adjusted_scores.get(heuristic, 0)
            if current_score - alternate_score <= 1:
                decision = alternate_agent
                logger.debug(
                    f"Supervisor(step={step}) second_intent={alternate_agent} "
                    f"score={alternate_score} current={current_score}"
                )

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
    worker_messages = list(state["messages"][-_WORKER_INPUT_MESSAGE_LIMIT:])
    if worker_messages and not isinstance(worker_messages[0], HumanMessage):
        worker_messages = worker_messages[1:]
    if not worker_messages and state["messages"]:
        worker_messages = [state["messages"][-1]]
    result = await agent.ainvoke(
        {"messages": [SystemMessage(content=WORKER_PROMPTS[agent_key]), *worker_messages]}
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
    """聚合已执行 Worker 的结果；是否进入该节点由 graph 条件路由决定。"""
    worker_results = _extract_worker_results(state)

    result_sections = []
    for agent_key, content in worker_results:
        label = AGENT_LABELS.get(agent_key, agent_key)
        result_sections.append(f"{label}:\n{content}")

    user_text = _latest_user_text(state)
    llm = get_llm(streaming=True)
    response = await llm.ainvoke(
        [
            SystemMessage(content=SYNTHESIZE_PROMPT),
            HumanMessage(
                content=(
                    f"用户问题：\n{user_text or '（未获取到用户问题）'}\n\n"
                    "Agent 执行结果：\n"
                    + ("\n\n---\n\n".join(result_sections) or "（无 Worker 结果）")
                )
            ),
        ]
    )
    return {"messages": [response]}
