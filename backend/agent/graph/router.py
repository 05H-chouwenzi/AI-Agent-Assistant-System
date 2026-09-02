"""LangGraph 路由：关键词评分 + 置信度阈值 + LLM 兜底

优化方案：高置信度规则路由跳过 Supervisor LLM，降低调用次数。"""
import re
from typing import Literal, Tuple, Union

MessageContent = Union[dict, object]

RouteTarget = Literal["research", "data", "general", "synthesize", "FINISH"]

MAX_GRAPH_STEPS = 6

# ====== 配置：高置信度阈值 ======
HIGH_CONFIDENCE_THRESHOLD = 5  # 评分≥5 判定为高置信度，直接规则路由

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
    "synthesize": "Synthesizer · 最终回答",
}


def score_keywords(text: str, keywords: list[tuple[str, int]]) -> int:
    """基于关键词列表计算文本的关键词得分"""
    text_lower = text.lower()
    return sum(weight for kw, weight in keywords if kw in text_lower)


def heuristic_route(text: str, route_history: list[str]) -> Tuple[RouteTarget, int]:
    """
    基于关键词评分的启发式路由，返回 (路由目标，置信度得分)
    已执行过的 Agent 降权（避免重复）
    """
    scores = {
        "research": score_keywords(text, RESEARCH_KEYWORDS),
        "data": score_keywords(text, DATA_KEYWORDS),
        "general": score_keywords(text, GENERAL_KEYWORDS),
    }
    
    # 对历史路由过的 Agent 降权
    for agent in route_history:
        if agent in scores:
            scores[agent] = max(0, scores[agent] - 2)
    
    best = max(scores, key=scores.get)
    
    # 若无任何匹配 → general
    if scores[best] == 0:
        return "general", 0
    
    return best, scores[best]


def should_finish(step_count: int, route_history: list[str], last_agent: str | None) -> bool:
    """安全阀：步数上限或重复路由"""
    if step_count >= MAX_GRAPH_STEPS:
        return True
    if last_agent and len(route_history) >= 2 and route_history[-1] == last_agent:
        return True
    return False


def _get_msg_content(msg: MessageContent) -> str:
    """获取消息内容字符串，兼容 dict 和对象两种格式"""
    if isinstance(msg, dict):
        return msg.get("content", "")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
        return str(content)
    return ""


def _is_worker_message(msg: MessageContent, allowed_agents: set) -> bool:
    """判断是否为 Worker 的消息"""
    if isinstance(msg, dict):
        additional = msg.get("additional_kwargs", {})
        agent = additional.get("agent", "")
        return agent in allowed_agents
    if hasattr(msg, "additional_kwargs") and hasattr(msg.additional_kwargs, "get"):
        agent = getattr(msg.additional_kwargs, "get", lambda x, d=""): x
        return agent in allowed_agents
    return False


def worker_can_finish(state) -> bool:
    """
    Worker 完成后判断是否可以结束。
    
    简单策略（无需调用 LLM）：
    - Research/Data/General 首次执行后：如果问题明确单一，可以直接返回答案
    - 但保留多轮协作的空间：若用户暗示需要多个来源，或问题较复杂，则继续
    
    返回：True=可以结束，False=需要 Supervisor 继续调度
    """
    messages = state.get("messages", [])
    history = state.get("route_history", [])
    last_worker = state.get("last_worker", "")
    
    # 第一步：检查是否有多个 Agent 被调度过（复杂任务标志）
    if len(history) >= 2:
        # 已经调度了多个 Agent → 可能需要 Synthesize
        return False
    
    # 第二步：获取 Worker 最新回复（从后往前找第一个 Worker 消息）
    latest_worker_msg = None
    allowed_agents = {"research", "data", "general"}
    
    for msg in reversed(messages):
        if _is_worker_message(msg, allowed_agents):
            latest_worker_msg = msg
            break
    
    if not latest_worker_msg:
        return False
    
    # 第三步：规则判断是否可以结束
    content = _get_msg_content(latest_worker_msg)
    
    # Research Worker：如果包含引用来源或"根据 xxx 文档/手册/知识库"，说明已有完整答案
    if last_worker == "research":
        research_indicators = ["根据", "在", "文档", "手册", "知识库", "规定", "制度", "条款", "原文", "来源"]
        has_source = any(indicator in content for indicator in research_indicators)
        if has_source and "?" not in content[:50]:
            return True  # 有明确引用来源且未提新问题
    
    # Data Worker：如果有具体数据、数字、结论，通常可以结束
    if last_worker == "data":
        data_indicators = ["元", "个", "条", "份", "人", "金额", "万元", "%", "总计", "平均"]
        has_data = any(indicator in content for indicator in data_indicators)
        if has_data and "?" not in content[:50]:
            return True
    
    # General Worker：如果回答是完整句子且无追问提示
    if last_worker == "general":
        if "?" not in content and len(content.split()) > 5:
            return True
    
    # 默认：不确定时不急于结束，给 Supervisor 决策空间
    return False


def build_supervisor_context(route_history: list[str], step_count: int) -> str:
    history = " → ".join(route_history) if route_history else "（尚无）"
    return f"当前步数：{step_count}/{MAX_GRAPH_STEPS}，已执行路由：{history}"


SUPERVISOR_PROMPT = """你是企业 AI Agent 平台的 Supervisor（任务调度器）。

## 可用 Agent
- **research**：知识库检索、内部文档/政策/手册问答
- **data**：数据库只读查询、Excel/表格分析
- **general**：通用问答、天气等外部 API
- **FINISH**：信息已足够，可以给出最终答复（无需再调用 Agent）

## 规则
1. 分析用户最新问题，选择一个最合适的下一步
2. 若问题涉及多个领域，按优先级逐个调度（每次只选一个）
3. 若 Worker 已返回结果且足以回答用户，选择 FINISH
4. 简单寒暄、概念解释→general；查文档→research；查数/分析→data

## 输出格式
**只输出一个单词**：research / data / general / FINISH
不要解释，不要标点。"""

WORKER_PROMPTS = {
    "research": (
        "你是 Research Agent，专注企业知识库检索与文档问答。\n"
        "规则：优先调用 rag_search 工具检索知识库；引用来源；找不到时明确说明。\n格式：用普通文本，不要 Markdown 格式、# 标题、| 表格、** 粗体、--- 分隔线；直接用简洁段落"
    ),
    "data": (
        "你是 Data Agent，专注只读 SQL 与数据分析。\n"
        "规则：优先调用 mysql 工具查询数据库获取真实数据；禁止编造数字；无法查询时说明原因。\n格式：用普通文本，不要 Markdown 格式、# 标题、| 表格、** 粗体、--- 分隔线；直接用简洁段落"
    ),
    "general": (
        "你是 General Agent，处理通用问答与外部 API。\n"
        "规则：简洁准确；需要实时天气信息时必须调用 weather 工具获取，禁止编造天气。\n格式：用普通文本，不要 Markdown 格式、# 标题、| 表格、** 粗体、--- 分隔线；直接用简洁段落"
    ),
}

SYNTHESIS_PROMPT = """你是企业 AI Agent 平台的最终回答合成器（Synthesizer）。
根据对话中各 Worker Agent 的检索、分析结果，为用户生成完整、结构化的最终回答。
要求：中文、专业、简洁、用普通文本；若有多个来源请整合；不要提及内部 Agent 名称。"""


def parse_supervisor_decision(raw: str) -> RouteTarget | None:
    """解析 Supervisor LLM 输出的决策文本，返回标准化路由目标"""
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


def route_from_supervisor(state) -> str:
    """Supervisor 路由选择 → 解析后的目标
    
    核心逻辑：
    - 单个 Worker 完成后选择 FINISH → 直接返回该 Worker 结果
    - 多个 Worker 完成后选择 FINISH → 进入 Synthesize 综合整理
    """
    nxt = state.get("next_agent", "general")
    history = state.get("route_history", [])
    
    if nxt in ("FINISH", "finish"):
        if not history:
            # 第一次路由就直接说 Finish → 走通用 Agent
            return "general"
        elif len(history) <= 1:
            # 只调度过 1 个 Worker → 直接返回该 Worker 的结果
            return "end"
        else:
            # 调度过多个 Worker → 需要 Synthesize 综合
            return "synthesize"
    
    if nxt in ("research", "data", "general", "synthesize"):
        return nxt
    return "general"


def route_after_worker(state) -> str:
    """Worker 完成后先判断是否可以直接结束，否则回到 Supervisor"""
    # Step 1: Worker 完成后的快速判断
    if worker_can_finish(state):
        return "end"
    
    # Step 2: 步数上限强制结束
    step = state.get("step_count", 0)
    if step >= MAX_GRAPH_STEPS:
        return "synthesize"
    
    # Step 3: 回 Supervisor 继续调度
    return "supervisor"
