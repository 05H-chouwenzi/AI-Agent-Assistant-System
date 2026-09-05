"""LangGraph 路由：关键词评分 + LLM 决策解析

完全匹配 ai-agent 架构。
"""
import logging
from dataclasses import dataclass, field
import re
from typing import Literal

RouteTarget = Literal["research", "data", "general", "FINISH"]

# 最大 Worker 调度次数（按已完成的 Worker 执行数计，而非 Supervisor 进入次数）
MAX_GRAPH_STEPS = 2

# 路由调试日志：独立 logger + 控制台 handler，保证 [ROUTE_DEBUG] 始终可见
_route_logger = logging.getLogger("route_debug")
if not _route_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _route_logger.addHandler(_handler)
_route_logger.setLevel(logging.INFO)
_route_logger.propagate = False

#
# ===== Research 综合评分配置（30 个企业知识库主题） =====
#
# 评分模型：主题词 × 企业制度查询意图 × 公司上下文
#   - 强主题词 +2~+3，普通主题词 +1（跨主题可累加，全局封顶）
#   - 一般疑问意图 +1（封顶 2），企业制度意图 +2（封顶 4）
#   - 公司/员工上下文 +2（封顶 2）
#   - 命中明确 Data 意图词 → 抑制 Research；分句复合意图保留两条证据
#   - 只有主题词 + 意图/上下文 组合才可能达到路由阈值（>=2）
#

RESEARCH_TOPICS: dict[str, list[tuple[str, int]]] = {
    "员工手册": [
        ("员工手册", 3), ("行为规范", 3), ("企业文化", 3), ("职业操守", 3),
        ("员工义务", 3), ("保密制度", 3), ("员工", 1),
    ],
    "招聘录用": [
        ("招聘", 2), ("录用", 2), ("面试", 2), ("简历", 2), ("offer", 2),
        ("入职", 2), ("试用期", 2), ("转正", 2), ("招聘审批", 3),
    ],
    "考勤休假": [
        ("考勤", 2), ("打卡", 2), ("迟到", 2), ("早退", 2), ("旷工", 2),
        ("年假", 2), ("病假", 2), ("事假", 2), ("婚假", 2), ("产假", 2),
        ("陪产假", 2), ("请假", 2), ("休假", 2), ("调休", 2),
    ],
    "薪酬福利": [
        ("工资", 2), ("薪酬", 2), ("绩效工资", 2), ("津贴", 2), ("交通补贴", 2),
        ("通讯补贴", 2), ("餐补", 2), ("奖金", 2), ("年终奖", 3), ("福利", 2),
        ("五险一金", 2), ("社保", 2), ("公积金", 2), ("发薪日", 3), ("补贴", 1),
    ],
    "培训发展": [
        ("培训", 2), ("入职培训", 2), ("技能培训", 2), ("导师", 2), ("课程", 2),
        ("讲师", 2), ("培训计划", 2), ("人才培养", 3), ("能力提升", 2), ("学习", 1),
    ],
    "绩效考核": [
        ("绩效", 2), ("kpi", 2), ("okr", 2), ("考核", 2), ("评分", 1),
        ("绩效面谈", 3), ("晋升", 2), ("调薪", 2), ("绩效改进", 2), ("绩效结果", 2),
    ],
    "办公资产": [
        ("工位", 2), ("办公用品", 2), ("显示器", 2), ("打印机", 2), ("固定资产", 3),
        ("报修", 2), ("电脑", 1), ("领用", 1), ("借用", 1), ("归还", 1), ("设备", 1),
    ],
    "印章证照": [
        ("公章", 3), ("合同章", 3), ("财务章", 3), ("法人章", 3), ("印章", 3),
        ("用印", 3), ("盖章", 2), ("证照", 2), ("营业执照", 2), ("资质证书", 2),
    ],
    "财务报销": [
        ("费用标准", 3), ("报销标准", 3), ("差旅费", 3), ("住宿费", 2), ("发票", 2),
        ("差旅", 2), ("交通费", 2), ("机票", 2), ("高铁", 2), ("票据", 2),
        ("报销", 1), ("出差", 1), ("住宿", 1),
    ],
    "采购供应商": [
        ("采购申请", 3), ("采购审批", 3), ("采购", 2), ("询价", 2), ("比价", 2),
        ("招标", 2), ("供应商", 2), ("准入", 2), ("供货", 2), ("入库", 1),
    ],
    "合同法务": [
        ("法律审核", 3), ("合同模板", 3), ("合同审批", 3), ("法务", 2), ("违约", 2),
        ("合同", 1), ("协议", 1), ("争议", 1), ("签订", 1), ("归档", 1), ("用印", 2),
    ],
    "知识产权": [
        ("知识产权", 3), ("职务成果", 3), ("专利", 2), ("著作权", 2), ("商标", 2),
        ("源代码", 2), ("版权", 2), ("侵权", 2), ("算法", 1), ("发明", 1),
    ],
    "反商业贿赂": [
        ("商业贿赂", 3), ("礼金", 3), ("回扣", 3), ("利益冲突", 3), ("礼品", 2),
        ("宴请", 2), ("廉洁", 2), ("礼物", 2), ("红包", 2), ("招待", 2),
    ],
    "IT网络安全": [
        ("白名单", 3), ("信息安全", 3), ("钓鱼", 3), ("密码", 2), ("内网", 2),
        ("网络权限", 2), ("病毒", 2), ("补丁", 2), ("上网", 2),
        ("vpn", 1), ("软件", 1), ("安装", 1), ("账号", 1), ("it", 1), ("网络", 1),
    ],
    "数据保密": [
        ("数据安全", 3), ("商业秘密", 3), ("机密", 3), ("数据泄露", 3), ("泄密", 3),
        ("保密", 2), ("客户信息", 2), ("财务数据", 2), ("源代码", 2), ("加密", 2),
    ],
    "对外宣传": [
        ("对外发声", 3), ("宣传", 2), ("媒体", 2), ("采访", 2), ("发言人", 2),
        ("社交媒体", 2), ("微博", 2), ("抖音", 2), ("舆情", 2), ("公众号", 2),
        ("新闻", 1), ("微信", 1),
    ],
    "突发应急": [
        ("火灾", 3), ("消防", 3), ("逃生", 3), ("疏散", 3), ("灭火器", 3),
        ("急救", 2), ("工伤", 2), ("事故", 2), ("应急", 2), ("灾害", 2),
        ("报警", 2), ("119", 1), ("120", 1),
    ],
    "职业安全": [
        ("安全生产", 3), ("职业健康", 3), ("安全操作", 3), ("特种作业", 3),
        ("安全隐患", 3), ("责任制", 2), ("实验室", 2), ("化学品", 2), ("ppe", 2),
        ("防护用品", 2), ("劳保", 2),
    ],
    "客服SOP": [
        ("sla", 3), ("服务标准", 3), ("紧急投诉", 3), ("客服", 2), ("投诉", 2),
        ("话术", 2), ("响应时效", 2), ("客诉", 2), ("客户服务", 1), ("工单", 1),
    ],
    "项目管理": [
        ("项目计划", 3), ("项目复盘", 3), ("立项", 2), ("里程碑", 2), ("项目进度", 2),
        ("项目变更", 2), ("项目验收", 2), ("结项", 2), ("项目", 1), ("项目经理", 1),
    ],
    "会议管理": [
        ("会议纪要", 3), ("例会", 2), ("议程", 2), ("参会", 2), ("会议室", 2),
        ("会议安排", 2), ("会议决议", 2), ("周会", 2), ("月会", 2), ("会议", 1),
    ],
    "档案文件": [
        ("文档管理", 3), ("档案室", 3), ("档案", 2), ("借阅", 2), ("销毁", 2),
        ("存档", 2), ("归档", 1), ("文件", 1), ("资料", 1),
    ],
    "访客门禁": [
        ("门禁卡", 3), ("受限区域", 3), ("访客登记", 3), ("访客", 2), ("门禁", 2),
        ("来访", 2), ("机房", 2), ("接待", 1),
    ],
    "销售客户": [
        ("客户交接", 3), ("销售", 2), ("商机", 2), ("报价", 2), ("折扣", 2),
        ("客户资料", 2), ("crm", 2), ("客户跟进", 2), ("回款", 2), ("合同额", 2),
        ("客户", 1),
    ],
    "产品质量": [
        ("质量问题", 3), ("质量标准", 3), ("质量投诉", 3), ("质量", 2), ("质检", 2),
        ("缺陷", 2), ("整改", 2), ("良率", 2), ("抽检", 2), ("不良品", 2), ("产品", 1),
    ],
    "仓储物流": [
        ("仓库", 2), ("库存", 2), ("出库", 2), ("盘点", 2), ("物流", 2), ("发运", 2),
        ("物料", 2), ("发货", 2), ("入库", 1), ("领用", 1), ("成品", 1),
    ],
    "环境管理": [
        ("垃圾分类", 3), ("电子废弃物", 3), ("绿色办公", 3), ("环保", 2), ("节能", 2),
        ("废弃物", 2), ("能耗", 2), ("碳排放", 2), ("环境", 1),
    ],
    "合规举报": [
        ("举报", 3), ("舞弊", 3), ("打击报复", 3), ("举报渠道", 3), ("违规", 2),
        ("合规", 2), ("审计", 2), ("调查", 1),
    ],
    "车辆管理": [
        ("公务车", 3), ("交通事故", 3), ("车辆保养", 2), ("车辆维修", 2), ("车辆", 2),
        ("用车", 2), ("停车费", 2), ("过路费", 2), ("油费", 2), ("驾驶", 1),
        ("维修", 1), ("保养", 1),
    ],
    "信息系统": [
        ("系统故障", 3), ("数据备份", 3), ("oa", 2), ("erp", 2), ("crm", 2),
        ("操作日志", 2), ("系统权限", 2), ("审批系统", 2), ("账号开通", 2),
        ("系统账号", 2), ("系统", 1), ("权限", 1), ("工单", 1),
    ],
}

# 一般疑问意图（+1，封顶 2）：单独出现不足以路由，需与主题词组合
RESEARCH_INTENT_GENERAL: tuple[str, ...] = (
    "怎么", "如何", "怎么办", "多少", "几天", "几次", "多久", "什么时候",
    "哪些", "有没有", "能不能", "可以吗", "能否", "是否", "可不可以", "行不行",
)

# 企业制度查询意图（+2，封顶 4）：询问规定/流程/审批等强 Research 语义
RESEARCH_INTENT_STRONG: tuple[str, ...] = (
    "标准", "规定", "要求", "流程", "申请", "审批", "报销", "制度", "规则",
    "办法", "细则", "政策", "条件", "资格", "限制", "补贴",
    "需要什么", "需要谁", "需要哪些", "需要提供", "需要准备", "什么材料",
    "哪些材料", "什么条件", "谁审批", "怎么报", "如何报",
)

# 强意图正则模式：制度时效/办理时长类问题（如"合同审核需要多久"）
RESEARCH_INTENT_STRONG_PATTERNS: tuple[str, ...] = (
    r"需要.{0,4}(?:多久|多长时间|多少天|几个工作日)",
    r"多久.{0,6}(?:能|可以|会)?(?:批|审批|审核|通过|到账|发放|报销|下来|完成)",
    r"多长时间.{0,4}(?:能|可以|会)?(?:批|审批|通过|到账|发放)",
)

# 公司/员工上下文（+2，封顶 2）：明确指向企业内部制度语境
RESEARCH_CONTEXT_WORDS: tuple[str, ...] = ("公司", "本公司", "咱们公司", "我们公司", "内部")

RESEARCH_CONTEXT_PATTERNS: tuple[str, ...] = (
    r"公司(规定|制度|要求|允许|有没有|标准|流程|需要审批|是否允许)",
    r"(按照|根据)公司",
    r"公司的.{0,8}(制度|流程|标准|规定)",
    r"员工(可以|能否|能不能|怎么|怎么办|如何)",
    r"需要谁(审批|批准|审核)",
    r"需要什么(材料|资料|手续|条件|流程)",
    r"(能|可以)报销多少",
    r"有没有(补贴|补助|津贴)",
)

# 明确 Data 意图；非复合请求时抑制 Research，Data 优先级保留
DATA_PRIORITY_KEYWORDS: tuple[str, ...] = (
    "sql", "数据库查询", "数据统计", "数据分析", "统计数量", "统计趋势",
    "统计", "查询", "报表", "趋势", "汇总", "环比", "同比", "占比",
    "筛选", "数据量", "计算数量", "图表", "excel", "csv", "xlsx", "数据表",
)

_TOPIC_SCORE_CAP = 8
_INTENT_SCORE_CAP = 4
_CONTEXT_SCORE_CAP = 2
_RESEARCH_SCORE_CAP = 10
_RESEARCH_MIN_TOTAL = 2  # 低于该值视为 Research 得分不足 → General 兜底


@dataclass
class ResearchScore:
    """Research 综合评分结果（用于路由决策与 Debug 日志）"""
    score: int = 0
    matched_topics: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    topic_score: int = 0
    intent_score: int = 0
    context_score: int = 0
    data_suppressed: bool = False
    multi_intent: bool = False


def _contains_keyword(text_lower: str, keyword: str) -> bool:
    """中文用子串匹配；纯 ASCII 词（oa/kpi/vpn...）按整词边界匹配，避免误命中"""
    if keyword.isascii():
        return re.search(rf"\b{re.escape(keyword)}\b", text_lower) is not None
    return keyword in text_lower


# Compound intent detection uses independent clause evidence. Generic data action
# words such as "查询"/"统计" are only treated as Data evidence when paired with a
# measurable data object, so a pure policy lookup is not mistaken for SQL.
_GENERIC_DATA_OPERATIONS = ("查询", "统计")
_DATA_METRIC_KEYWORDS = (
    "销售额", "数量", "金额", "费用", "成本", "收入", "利润", "人数",
    "订单", "指标", "数据", "记录", "总量", "平均值", "环比", "同比", "占比",
)
_COMPOUND_INTENT_SEPARATORS = re.compile(
    r"[，,；;。！？\n]+|并且|而且|同时|以及|另外"
)


def _split_intent_clauses(text: str) -> list[str]:
    return [
        clause.strip()
        for clause in _COMPOUND_INTENT_SEPARATORS.split(text)
        if clause.strip()
    ]


def _has_strong_data_intent(text_lower: str) -> bool:
    specific_keywords = tuple(
        keyword for keyword in DATA_PRIORITY_KEYWORDS
        if keyword not in _GENERIC_DATA_OPERATIONS
    )
    if any(_contains_keyword(text_lower, keyword) for keyword in specific_keywords):
        return True
    has_operation = any(keyword in text_lower for keyword in _GENERIC_DATA_OPERATIONS)
    has_metric = any(keyword in text_lower for keyword in _DATA_METRIC_KEYWORDS)
    return has_operation and has_metric


def _has_strong_research_evidence(score: ResearchScore) -> bool:
    return (
        (score.topic_score >= 2 and score.intent_score >= 2)
        or (score.topic_score >= 3 and (score.intent_score >= 1 or score.context_score >= 2))
    )


def _has_compound_research_data_intent(text: str) -> bool:
    """Require Research and Data evidence in different clauses of one request."""
    clauses = _split_intent_clauses(text)
    if len(clauses) < 2:
        return False

    for index, clause in enumerate(clauses):
        research = _score_research_components(clause)
        if not _has_strong_research_evidence(research):
            continue
        for other_index, other_clause in enumerate(clauses):
            if other_index != index and _has_strong_data_intent(other_clause.lower()):
                return True
    return False


def _score_research_components(text: str) -> ResearchScore:
    """Score Research evidence before applying Data Priority suppression."""
    result = ResearchScore()
    text_lower = text.lower()
    matched_keywords: set[str] = set()

    # ---- 1) 主题词匹配（30 个企业知识库主题）----
    topic_score = 0
    for topic_name, keywords in RESEARCH_TOPICS.items():
        for keyword, weight in keywords:
            if _contains_keyword(text_lower, keyword):
                topic_score += weight
                matched_keywords.add(keyword)
                if topic_name not in result.matched_topics:
                    result.matched_topics.append(topic_name)
    topic_score = min(topic_score, _TOPIC_SCORE_CAP)

    # ---- 2) 企业制度查询意图 ----
    intent_score = 0
    for keyword in RESEARCH_INTENT_GENERAL:
        if keyword in matched_keywords:
            continue  # 已作为主题词命中，不重复计分
        if keyword in text_lower:
            intent_score += 1
            matched_keywords.add(keyword)
    intent_score = min(intent_score, 2)
    for keyword in RESEARCH_INTENT_STRONG:
        if keyword in matched_keywords:
            continue
        if keyword in text_lower:
            intent_score += 2
            matched_keywords.add(keyword)
    intent_score = min(intent_score, _INTENT_SCORE_CAP)

    # ---- 3) 公司/员工上下文（词 + 正则语义模式）----
    context_score = 0
    for word in RESEARCH_CONTEXT_WORDS:
        if word in text_lower:
            context_score = _CONTEXT_SCORE_CAP
            matched_keywords.add(word)
            break
    if context_score == 0:
        for pattern in RESEARCH_CONTEXT_PATTERNS:
            if re.search(pattern, text_lower):
                context_score = _CONTEXT_SCORE_CAP
                matched_keywords.add("制度语义模式")
                break

    # 制度时效类强意图（需要多久 / 多久能审批...）
    for pattern in RESEARCH_INTENT_STRONG_PATTERNS:
        if re.search(pattern, text_lower):
            intent_score += 2
            matched_keywords.add("时效意图")
            break

    result.topic_score = min(topic_score, _TOPIC_SCORE_CAP)
    result.intent_score = min(intent_score, _INTENT_SCORE_CAP)
    result.context_score = context_score
    result.matched_topics = list(result.matched_topics)
    result.matched_keywords = sorted(matched_keywords)
    return result


def score_research(text: str) -> ResearchScore:
    """Research 综合评分：主题词 + 企业制度查询意图 + 公司上下文 - Data 抑制"""
    result = _score_research_components(text)
    text_lower = text.lower()

    # ---- 4) 明确 Data 意图 → Research 直接抑制（Data 优先）----
    has_data_priority = any(_contains_keyword(text_lower, kw) for kw in DATA_PRIORITY_KEYWORDS)
    multi_intent = _has_compound_research_data_intent(text)
    data_suppressed = has_data_priority and not multi_intent

    total = result.topic_score + result.intent_score + result.context_score
    total = min(total, _RESEARCH_SCORE_CAP)

    # 门槛：孤立主题词 + 弱疑问（无制度意图/公司上下文）不足以路由 Research
    has_intent_or_context = result.intent_score >= 2 or result.context_score >= 2
    if total > 0 and (result.topic_score < 2 and not has_intent_or_context):
        total = min(total, _RESEARCH_MIN_TOTAL - 1)
    if data_suppressed:
        total = 0

    result.score = total
    result.data_suppressed = data_suppressed
    result.multi_intent = multi_intent
    return result


class _ResearchScorer:
    """哨兵类型：score_keywords(RESEARCH_KEYWORDS) 时自动走 Research 综合评分"""
    __slots__ = ()


# 兼容旧接口：nodes.py 通过 score_keywords(text, RESEARCH_KEYWORDS) 获取 Research 分数
RESEARCH_KEYWORDS = _ResearchScorer()

DATA_KEYWORDS = [
    ("sql", 3), ("数据库", 3), ("查询", 2), ("表", 1), ("excel", 3),
    ("表格", 2), ("统计", 2), ("分析", 2), ("数据", 2), ("报表", 2),
    ("xlsx", 3), ("csv", 2), ("销售额", 2), ("指标", 1), ("订单", 2),
    ("用户数据", 2), ("查询表", 2),
    ("金额", 2), ("费用", 2), ("成本", 2), ("收入", 2), ("利润", 2),
    ("人数", 2), ("数量", 2),
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
    if isinstance(keywords, _ResearchScorer):
        return score_research(text).score
    text_lower = text.lower()
    return sum(weight for kw, weight in keywords if kw in text_lower)


def heuristic_route(text: str, route_history: list[str]) -> RouteTarget:
    """基于关键词评分的启发式路由，已执行过的 Agent 降权"""
    research = score_research(text)
    scores: dict[str, int] = {
        "research": research.score,
        "data": score_keywords(text, DATA_KEYWORDS),
        "general": score_keywords(text, GENERAL_KEYWORDS),
    }
    for agent in route_history:
        if agent in scores:
            scores[agent] = max(0, scores[agent] - 2)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "general"

    # After one worker has run, let a close unexecuted candidate win the repeat
    # decision. Otherwise a strong compound request can repeat/finish early.
    executed = set(route_history)
    alternate_scores = [
        (agent, score) for agent, score in scores.items()
        if agent not in executed
    ]
    if executed and alternate_scores:
        alternate_agent, alternate_score = max(
            alternate_scores, key=lambda item: item[1]
        )
        if alternate_score >= max(2, scores[best] - 2):
            best = alternate_agent

    # ---- ROUTE_DEBUG：每次 Supervisor 首次路由输出，便于误路由定位 ----
    sorted_vals = sorted(scores.values(), reverse=True)
    second_val = sorted_vals[1] if len(sorted_vals) > 1 else 0
    diff = sorted_vals[0] - second_val
    if sorted_vals[0] >= 3 and diff >= 3:
        confidence = "high"
    elif diff >= 2:
        confidence = "medium"
    else:
        confidence = "low"
    _route_logger.info(
        "[ROUTE_DEBUG]\n"
        f"question={text}\n"
        f"research_score={scores['research']}\n"
        f"data_score={scores['data']}\n"
        f"general_score={scores['general']}\n"
        f"matched_topics={research.matched_topics}\n"
        f"matched_keywords={research.matched_keywords}\n"
        f"data_suppressed={research.data_suppressed}\n"
        f"multi_intent={research.multi_intent}\n"
        f"route={best}\n"
        f"confidence={confidence}"
    )
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
    """安全阀：按已完成 Worker 数限制循环，或重复路由"""
    if len(route_history) >= MAX_GRAPH_STEPS:
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
        "规则：优先调用 rag_search；引用来源；找不到时明确说明。"
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
