"""LangGraph 路由：关键词评分 + LLM 决策解析

完全匹配 ai-agent 架构。
"""
import re
from typing import Literal

RouteTarget = Literal["research", "data", "general", "FINISH"]

MAX_GRAPH_STEPS = 6

RESEARCH_KEYWORDS = [
    ("知识库", 3), ("文档", 2), ("手册", 2), ("政策", 2), ("规章", 2),
    ("制度", 3), ("规定", 2), ("内部", 1), ("资料", 1), ("检索", 2),
    ("查找", 1), ("条款", 2), ("说明书", 2), ("pdf", 2), ("word", 1),
    ("公司", 1), ("员工手册", 3), ("请假", 2), ("报销", 2),
]

DATA_KEYWORDS = [
    ("sql", 3), ("数据库", 3), ("查询", 2), ("表", 1), ("excel", 3),
    ("表格", 2), ("统计", 2), ("分析", 2), ("数据", 2), ("报表", 2),
    ("xlsx", 3), ("csv", 2), ("销售额", 2), ("指标", 1), ("订单", 2),
    ("用户数据", 2), ("查询表", 2),
]

GENERAL_KEYWORDS = [
    ("天气", 3), ("温度", 2), ("你好", 1), ("介绍", 1), ("是什么", 1),
    ("帮我", 1), ("解释", 1), ("翻译", 2), ("总结", 1), ("hi", 1),
    ("hello", 1), ("计算", 2), ("多少", 1),
]

AGENT_LABELS = {
    "research": "Research Agent · 知识检索",
    "data": "Data Agent · 数据分析",
    "general": "General Agent · 通用助手",
}


def score_keywords(text: str, keywords: list[tuple[str, int]]) -> int:
    text_lower = text.lower()
    return sum(weight for kw, weight in keywords if kw in text_lower)


def heuristic_route(text: str, route_history: list[str]) -> RouteTarget:
    """基于关键词评分的启发式路由，已执行过的 Agent 降权"""
    scores = {
        "research": score_keywords(text, RESEARCH_KEYWORDS),
        "data": score_keywords(text, DATA_KEYWORDS),
        "general": score_keywords(text, GENERAL_KEYWORDS),
    }
    for agent in route_history:
        if agent in scores:
            scores[agent] = max(0, scores[agent] - 2)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "general"
    return best


def parse_supervisor_decision(raw: str) -> RouteTarget | None:
    if not raw:
        return None
    text = raw.strip().lower()
    for target in ("finish", "research", "data", "general"):
        if re.search(rf"\b{target}\b", text):
            return "FINISH" if target == "finish" else target
    aliases = {
        "研究": "research", "检索": "research", "知识": "research",
        "数据": "data", "分析": "data", "查询": "data",
        "通用": "general", "完成": "FINISH", "结束": "FINISH",
    }
    for alias, target in aliases.items():
        if alias in text:
            return target
    return None


def should_finish(step_count: int, route_history: list[str], last_agent: str | None) -> bool:
    """安全阀：步数上限或重复路由"""
    if step_count >= MAX_GRAPH_STEPS:
        return True
    if last_agent and len(route_history) >= 2 and route_history[-1] == last_agent:
        return True
    return False


def build_supervisor_context(route_history: list[str], step_count: int) -> str:
    history = " → ".join(route_history) if route_history else "（尚无）"
    return f"当前步数: {step_count}/{MAX_GRAPH_STEPS}，已执行路由: {history}"


SUPERVISOR_PROMPT = """你是企业 AI Agent 平台的 Supervisor（任务调度器）。

## 可用 Agent
- **research**：知识库检索、内部文档/政策/手册问答
- **data**：数据库只读查询、Excel/表格分析
- **general**：通用问答、天气等外部 API
- **FINISH**：信息已足够，可以给出最终答复（无需再调用 Agent）

## 规则
1. 分析用户最新问题，选择**一个**最合适的下一步
2. 若问题涉及多个领域，按优先级逐个调度（每次只选一个）
3. 若 Worker 已返回结果且足以回答用户，选择 FINISH
4. 简单寒暄、概念解释 → general；查文档 → research；查数/分析 → data

## 输出格式
**只输出一个单词**：research / data / general / FINISH
不要解释，不要标点。"""

WORKER_PROMPTS = {
    "research": (
        "你是 Research Agent，专注企业知识库检索与文档问答。\n"
        "规则：优先调用 search_knowledge_base；引用来源；找不到时明确说明。"
    ),
    "data": (
        "你是 Data Agent，专注只读 SQL 与数据分析。\n"
        "规则：优先调用工具获取真实数据；禁止编造数字；无法查询时说明原因。"
    ),
    "general": (
        "你是 General Agent，处理通用问答与外部 API。\n"
        "规则：简洁准确；需要实时信息时使用 get_weather 等工具。"
    ),
}


def route_from_supervisor(state) -> str:
    """Supervisor 路由选择"""
    nxt = state.get("next_agent", "general")
    if nxt in ("FINISH", "finish"):
        return "end"
    if nxt in ("research", "data", "general"):
        return nxt
    return "general"


def route_after_worker(state) -> str:
    """Worker 完成后直接结束（不走第二次 supervisor）"""
    return "end"
