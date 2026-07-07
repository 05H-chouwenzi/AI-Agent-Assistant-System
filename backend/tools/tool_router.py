"""
Tool Router —— LLM function-calling 驱动的工具路由器

职责:
1. 接收用户问题 + 可用工具列表
2. 调用 LLM（带 function calling）决定调用哪个工具、传什么参数
3. 返回 (tool_name, tool_args) 供 ToolManager 执行

流程:
    User Question
        ↓
    ToolRouter.route(question, tool_schemas)
        ↓
    LLM (with function calling)
        ↓
    (tool_name, tool_args)
"""
import json
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
- mysql: 用于数据库查询（企业业务数据）
- http: 用于调用外部 API
- rag_search: 用于搜索企业内部知识库/文档"""


class ToolRouter:
    """
    工具路由器 —— 使用 LLM function calling 决定工具选择和参数

    用法:
        router = ToolRouter()
        tool_name, tool_args = router.route(question, tool_schemas)
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

    def route(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        根据用户问题，决定调用哪个工具以及参数

        参数:
            question: 用户问题
            tool_schemas: 可用工具的 function schema 列表
            history: 对话历史

        返回:
            (tool_name, tool_args) 或 (None, None) 表示不需要调用工具
        """
        if not tool_schemas:
            logger.info("ToolRouter: 没有可用工具，跳过")
            return None, None

        try:
            from openai import OpenAI
            from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL

            client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

            messages = [{"role": "system", "content": ROUTER_SYSTEM_PROMPT}]

            if history:
                # 只保留最近几轮
                recent = history[-6:]
                messages.extend(recent)

            messages.append({"role": "user", "content": question})

            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",  # LLM 自动决定是否调用工具
                temperature=0.1,      # 低温度，提高路由稳定性
            )

            choice = response.choices[0]
            message = choice.message

            # 检查是否有 tool_calls
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                func = tool_call.function
                tool_name = func.name
                try:
                    tool_args = json.loads(func.arguments)
                except json.JSONDecodeError:
                    logger.warning(f"ToolRouter: 参数解析失败: {func.arguments}")
                    tool_args = {}

                logger.info(f"ToolRouter: 选择工具 [{tool_name}], 参数: {tool_args}")
                return tool_name, tool_args

            # LLM 选择不调用任何工具
            logger.info(f"ToolRouter: LLM 决定不调用工具，直接回复: {message.content[:100] if message.content else '(无)'}")
            return None, None

        except Exception as e:
            logger.error(f"ToolRouter: 路由失败: {str(e)}")
            return None, None

    def route_with_fallback(
        self,
        question: str,
        tool_schemas: List[dict],
        history: Optional[List[dict]] = None,
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
        """
        带 fallback 的路由：如果用 function calling 失败，用简单关键词语义匹配

        返回:
            (tool_name, tool_args, fallback_reason)
        """
        tool_name, tool_args = self.route(question, tool_schemas, history)

        if tool_name is None:
            # 简单关键词 fallback
            tool_name, tool_args, reason = self._keyword_fallback(question, tool_schemas)
            if tool_name:
                return tool_name, tool_args, reason
            return None, None, None

        return tool_name, tool_args, None

    def _keyword_fallback(
        self, question: str, tool_schemas: List[dict]
    ) -> Tuple[Optional[str], Optional[Dict[str, Any]], str]:
        """关键词匹配兜底 —— 当 LLM function calling 不可用时的简单后备方案"""
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
                        # 提取参数
                        args = {}
                        if tool_name == "weather":
                            # 智能提取城市名：用正则匹配常见提问模式
                            import re

                            # 模式1：查询<城市>的天气 / 查<城市>天气
                            city = None
                            skip_words = ["根据", "工具", "中心", "api", "接口", "什么", "怎么", "如何", "一下", "交通"]
                            patterns = [
                                r'(?:查询|查|看看|搜|搜索)\s*(\w{2,6}?)\s*(?:的?天气|的?气温|的?温度)',
                                r'(\w{2,6}?)\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度)',
                            ]
                            for pat in patterns:
                                m = re.search(pat, question)
                                if m:
                                    candidate = m.group(1)
                                    # 过滤掉明显不是城市名的关键词
                                    if not any(w in candidate for w in skip_words):
                                        city = candidate
                                        break
                                    # 如果包含非城市词（如"北京交通"中的"交通"），尝试剔除
                                    for w in skip_words:
                                        if w in candidate:
                                            candidate = candidate.replace(w, "").strip()
                                    if candidate:
                                        city = candidate
                                        break

                            if not city:
                                # 模式2：取 "天气" 前最可能的词（去掉介词和提示词）
                                city_raw = question.split("天气")[0].strip() if "天气" in question else question
                                for t in ["明天", "后天", "今天", "昨天", "大后天", "未来", "一周", "一周内",
                                           "根据", "工具", "中心", "的", "api", "接口", "查询", "查", "一下",
                                           "交通", "请你"]:
                                    city_raw = city_raw.replace(t, "").strip()
                                city = city_raw if city_raw else question

                            args["city"] = city
                            # 默认只查当天
                            args["days"] = 1
                            # 智能判断天数
                            if any(w in question for w in ["后天", "大后天"]):
                                args["days"] = 3
                            elif any(w in question for w in ["明天", "未来"]):
                                args["days"] = 2
                        elif tool_name in ("mysql", "rag_search"):
                            args = {"query": question}
                        elif tool_name == "http":
                            args = {"url": question}
                        return tool_name, args, "keyword"

        return None, None, ""
