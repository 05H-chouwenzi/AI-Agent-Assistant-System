"""
Planner Node —— 判断任务类型（规则版，无需 LLM 调用）

用关键词匹配替代 LLM 调用，从 ~2-4s 降到 ~1ms。
如果匹配不到工具，会 fallback 到 tool_node 内部再调 LLM 路由。
"""
import re
from agent.state.agent_state import AgentState
from logs.logger import logger

# ============ RAG 关键词 ============
_RAG_KEYWORDS = [
    "知识库", "文档", "公司制度", "员工手册", "规章制度",
    "请假流程", "报销流程", "公司规定", "内部文档", "企业知识",
    "PDF", "文件", "手册", "政策", "规范", "档案",
    "知识", "公司", "制度", "规定",
    # 常见问法
    "查一下.*公司", "查一下.*制度", "公司.*规定", "有没有.*文档",
]

# ============ Tool 关键词 ============
_TOOL_KEYWORDS = [
    "天气", "股票", "新闻", "汇率", "实时", "最新",
    "查询", "搜索", "计算", "多少钱",
    "温度", "湿度", "涨停", "跌停", "股价",
    "美金", "欧元", "英镑", "日元",
    # 常见问法
    "今天.*天气", "查.*天气", "搜一下", "帮我查",
]


def _keyword_match(text: str, patterns: list[str]) -> bool:
    """用关键词或正则匹配"""
    text_lower = text.lower()
    for p in patterns:
        if p.isascii() and p == p.lower():  # 英文关键词简单包含
            if p in text_lower:
                return True
        elif ".*" in p:  # 正则模式
            if re.search(p, text, re.IGNORECASE):
                return True
        else:  # 中文关键词包含
            if p in text:
                return True
    return False


def planner_node(state: AgentState) -> AgentState:
    """用关键词快速判断任务类型，零 LLM 调用

    判断优先级：rag > tool > direct

    对于 tool 类型，不在 planner 中预选工具（省 LLM 调用），
    推迟到 tool_node 中统一处理。
    """
    question = state["question"]
    history = state.get("history", [])

    # 合并最近历史做上下文参考
    full_text = question
    if history:
        ctx = " ".join([
            m["content"][:100]
            for m in history[-2:]
        ])
        full_text = f"{ctx} {question}"

    # 1) 检查是否 RAG
    if _keyword_match(full_text, _RAG_KEYWORDS):
        task_type = "rag"
    # 2) 检查是否 Tool
    elif _keyword_match(full_text, _TOOL_KEYWORDS):
        task_type = "tool"
    # 3) 默认 direct
    else:
        task_type = "direct"

    state["task_type"] = task_type
    logger.info(f"Planner(规则) → {task_type}")
    return state
