"""
Tool Router —— 规则优先 + LLM function-calling 兜底的工具路由器

职责：
  1. 先用关键词规则快速匹配工具（零 LLM 调用）
  2. 规则无法判断时，降级到 LLM function calling
  3. 最终 fallback 到关键词兜底

架构：
    用户问题
        ↓
  关键词规则匹配
        ↓
    ┌────┴────┐
    │         │
  匹配成功   规则无法判断
    │         │
    │    LLM function calling
    │         │
    │     ┌───┴───┐
    │     │       │
    │   选择工具  无需工具
    │     │       │
    │   返回    直接回复
    │
  返回 (tool_name, tool_args)

  整个过程从原来的 100% 用 LLM（~2-4s）
  变为：规则优先（~1ms），仅规则无法判断时才调 LLM（~2-4s）
"""
import json
import re
from typing import Optional, Tuple, List, Dict, Any
from tools.base_tool import ToolResult
from logs.logger import logger

# ToolRouter 使用的系统提示词
ROUTER_SYSTEM_PROMPT = """你是一个智能工具路由助手。根据用户的问题，从可用工具中选择最合适的一个，并提供正确的参数。

规则：
1. 仔细分析用户问题的核心需求
2. 如果问题可以完全由 LLM 直接回答（常识问题、聊天、简单推理等），不要调用任何工具
3. 只在确实需要外部数据或特定能力时才调用工具
4. 参数值必须从用户问题中准确提取，不要编造
5. 如果用户问题涉及多个方面，选择最核心的需求对应的工具
6. 如果无法确定该用哪个工具，不要强行调用

注意：
- weather: 用于天气查询
- calculator: 用于数学计算
- mysql: 用于数据库查询（企业业务数据）
- http: 用于调用外部 API
- rag_search: 用于搜索企业内部知识库/文档"""


class ToolRouter:
    """
    工具路由器 —— 规则优先，LLM function calling 兜底

    用法:
        router = ToolRouter()
        tool_name, tool_args = router.route_with_rules(question, tool_schemas)
        if tool_name:
            result = tool_manager.execute(tool_name, **tool_args)
    """

    def __init__(self, model: Optional[str] = None):
        """
        model: LLM 模型名，默认从 config.settings 读取
        """
        if model is None:
            from config.settings import LLM_MODEL
            model = LLM_MODEL
        self._model = model

    def route_with_rules(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        规则优先路由：关键词规则 → LLM → 关键词兜底

        新的优先级排序：
          1. 关键词规则匹配（零 LLM 调用，~1ms）
          2. LLM function calling（~2-4s）
          3. 关键词兜底（零 LLM，~1ms）

        返回:
            (tool_name, tool_args, source)
            source: "rule" | "llm" | "fallback" | None
        """
        # 1️⃣ 先尝试关键词规则
        tool_name, tool_args = self._keyword_route(question, tool_schemas)
        if tool_name:
            logger.info(f"ToolRouter(规则): 命中 [{tool_name}], 参数: {tool_args}")
            return tool_name, tool_args, "rule"

        # 2️⃣ 规则未命中 → LLM function calling
        tool_name, tool_args = self._llm_route(question, tool_schemas, history)
        if tool_name:
            logger.info(f"ToolRouter(LLM): 选择 [{tool_name}], 参数: {tool_args}")
            return tool_name, tool_args, "llm"

        # 3️⃣ LLM 也未选择 → 关键词兜底
        tool_name, tool_args, reason = self._keyword_fallback(question, tool_schemas)
        if tool_name:
            logger.info(f"ToolRouter(兜底): 命中 [{tool_name}], 原因: {reason}")
            return tool_name, tool_args, "fallback"

        return None, None, None

    # ════════════════════════════════════════
    # 原有接口保留兼容
    # ════════════════════════════════════════

    def route(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """保留兼容：直接走 LLM function calling"""
        return self._llm_route(question, tool_schemas, history)

    def route_with_fallback(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """保留兼容：LLM → 关键词兜底

        返回:
            (tool_name, tool_args, fallback_reason)
        """
        tool_name, tool_args = self._llm_route(question, tool_schemas, history)
        if tool_name:
            return tool_name, tool_args, None

        # LLM 失败 → 关键词兜底
        tool_name, tool_args, reason = self._keyword_fallback(question, tool_schemas)
        if tool_name:
            return tool_name, tool_args, reason

        return None, None, None

    # ════════════════════════════════════════
    # 规则匹配（新增——零 LLM）
    # ════════════════════════════════════════

    def _keyword_route(
        self, question: str, tool_schemas: List[dict]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """关键词规则匹配 —— 从 tool_schemas 中查找名称匹配的工具

        比简单的关键词包含更精确，只在工具实际注册时才返回。
        """
        q = question.lower()
        available = {s.get("function", {}).get("name", "") for s in tool_schemas}

        # 规则匹配器字典：{工具名: 关键词列表}
        rule_map = {
            "weather":    ["天气", "气温", "温度", "下雨", "刮风", "下雪", "晴天", "阴天", "weather"],
            "calculator": ["计算", "加减乘除", "等于多少", "得多少", "运算"],
            "mysql":      ["数据库", "sql", "select", "统计", "报表", "查询表", "用户数据",
                           "订单", "多少条", "总金额", "金额",
                           "用户", "产品", "商品", "库存", "存货"],
            "http":       ["api", "接口", "http", "请求api", "调接口"],
            "rag_search": ["制度", "规定", "手册", "文档", "知识库", "政策", "流程",
                           "内部", "查询文档"],
        }

        for tool_name, keywords in rule_map.items():
            if tool_name not in available:
                continue
            for kw in keywords:
                if kw in q:
                    args = self._extract_args(tool_name, question)
                    return tool_name, args

        return None, None

    def _extract_args(self, tool_name: str, question: str) -> Dict[str, Any]:
        """为工具提取参数（基于简单规则）"""
        args = {}

        if tool_name == "weather":
            # 提取城市名
            city = None
            patterns = [
                r'(?:查询|查|看看|搜|搜索)\s*(\w{2,6}?)\s*(?:的?天气|的?气温|的?温度)',
                r'(\w{2,6}?)\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度)',
            ]
            for pat in patterns:
                m = re.search(pat, question)
                if m:
                    candidate = m.group(1)
                    skip = ["根据", "工具", "中心", "api", "接口", "什么", "怎么",
                            "如何", "一下", "交通", "查询", "查", "看看", "的",
                            "今天", "明天", "后天"]
                    if not any(w == candidate for w in skip):
                        city = candidate
                        break

            if not city:
                city_raw = question.split("天气")[0].strip() if "天气" in question else question
                for t in ["明天", "后天", "今天", "昨天", "大后天", "未来", "一周",
                          "根据", "工具", "的", "api", "接口", "查询", "查", "一下",
                          "交通", "请你", "请", "帮我"]:
                    city_raw = city_raw.replace(t, "").strip()
                city = city_raw if city_raw else question

            args["city"] = city
            args["days"] = 1
            if any(w in question for w in ["后天", "大后天"]):
                args["days"] = 3
            elif any(w in question for w in ["明天", "未来"]):
                args["days"] = 2

        elif tool_name == "mysql":
            # 尝试将自然语言转为 SQL
            q = question.lower()
            # 已知表名映射
            table_map = {
                "用户": "users",
                "订单": "orders",
                "产品": "products",
                "商品": "products",
                "库存": "inventory",
            }
            # 查找问题中提到的表
            matched_table = None
            for cn, en in table_map.items():
                if cn in q:
                    matched_table = en
                    break

            if matched_table:
                # 是否包含统计关键词
                if any(w in q for w in ["统计", "总共", "合计", "多少条", "数量"]):
                    args = {"query": f"SELECT COUNT(*) AS total FROM {matched_table}"}
                else:
                    args = {"query": f"SELECT * FROM {matched_table} LIMIT 20"}
            else:
                # 无法识别 → 传原文，让外层 LLM 处理
                args = {"query": question}

        elif tool_name == "rag_search":
            args = {"query": question}

        elif tool_name == "calculator":
            args = {"expression": question}

        elif tool_name == "http":
            # 尝试提取 URL
            url_match = re.search(r'https?://[^\s]+', question)
            args = {"url": url_match.group(0) if url_match else question, "method": "GET"}

        return args

    # ════════════════════════════════════════
    # LLM function calling（原有）
    # ════════════════════════════════════════

    def _llm_route(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """LLM function calling 路由（原 route 方法）"""
        if not tool_schemas:
            logger.info("ToolRouter(LLM): 没有可用工具，跳过")
            return None, None

        try:
            from openai import OpenAI
            from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL

            client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

            messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

            if history:
                recent = history[-6:]
                messages.extend(recent)

            messages.append({"role": "user", "content": question})

            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                temperature=0.1,
            )

            choice = response.choices[0]
            message = choice.message

            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                func = tool_call.function
                tool_name = func.name
                try:
                    tool_args = json.loads(func.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"ToolRouter(LLM): 参数解析失败: {func.arguments}")
                    tool_args = {}

                logger.info(f"ToolRouter(LLM): 选择工具 [{tool_name}], 参数: {tool_args}")
                return tool_name, tool_args

            logger.info(
                f"ToolRouter(LLM): 决定不调用工具: "
                f"{message.content[:100] if message.content else '(无)'}"
            )
            return None, None

        except Exception as e:
            logger.error(f"ToolRouter(LLM): 路由失败: {str(e)}")
            return None, None

    # ════════════════════════════════════════
    # 关键词兜底（原有逻辑保留）
    # ════════════════════════════════════════

    def _keyword_fallback(
        self, question: str, tool_schemas: List[dict]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
        """关键词匹配兜底 —— 当 LLM function calling 也不确定时的后备方案"""
        q = question.lower()

        keyword_map = {
            "weather": ["天气", "weather", "气温", "下雨", "刮风", "下雪", "晴天", "阴天", "温度"],
            "rag_search": ["制度", "规定", "手册", "文档", "知识库", "政策", "流程", "查询内部"],
            "mysql": ["数据库", "sql", "查询表", "select", "统计", "报表", "用户数据"],
            "http": ["api", "接口", "http", "请求", "爬取"],
        }

        for tool_name, keywords in keyword_map.items():
            for kw in keywords:
                if kw in q:
                    from tools.tool_manager import get_tool_manager
                    manager = get_tool_manager()
                    tool = manager.get(tool_name)
                    if tool:
                        args = self._extract_args(tool_name, question)
                        return tool_name, args, "keyword"

        return None, None, ""
