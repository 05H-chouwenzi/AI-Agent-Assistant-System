"""
FastRouter —— 规则快速路由

位置：整个流程最前面，在 Planner 之前。

职责：
  只识别非常明确的请求，用正则/关键词匹配替代 LLM 判断。
  匹配成功 → 直接调用对应的 Tool，跳过整个 Agent 流程（Planner → ToolRouter → LLM）。
  匹配失败 → 交给 Planner 继续走 Agent 流程。

架构：
    用户
      │
  FastRouter（规则）
      │              │
   命中             未命中
      │               │
    Tool         Planner（原有流程）
      │               │
  Formatter      ToolRouter
      │          （规则优先，LLM兜底）
      │               │
     返回            Tool
                      │
               是否需要 LLM？
                  │        │
                 否         是
                  │          │
              直接返回      LLM 总结
                              │
                             返回

支持的规则：
  1. 天气查询    → WeatherTool（例："北京天气"、"查上海天气"）
  2. 数学计算    → CalculatorTool（例："123+456"、"sqrt(64)"）
  3. 汇率查询    → HttpTool（例："美元汇率"）
  注：自然语言数据库查询（如"查询所有用户"、订单查询、库存查询等）走 Agent 流程，由 LLM 生成 SQL
"""
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from logs.logger import logger


# ==================== 规则定义 ====================

class FastRouteMatch:
    """FastRouter 匹配结果

    Attributes:
        tool_name:   要调用的工具名称
        tool_args:   工具参数字典
        rule_name:   匹配的规则名称（用于日志/追踪）
        is_final:    True=工具结果就是最终答案，无需再调 LLM
    """
    __slots__ = ("tool_name", "tool_args", "rule_name", "is_final")

    def __init__(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        rule_name: str,
        is_final: bool = True,
    ):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.rule_name = rule_name
        self.is_final = is_final


# ==================== 可配置的停用词 ====================
_SKIP_WORDS = {
    "根据", "工具", "中心", "api", "接口", "什么", "怎么", "如何",
    "一下", "交通", "查询", "查", "看看", "搜", "搜索", "的",
    "今天", "明天", "后天", "帮我", "请", "请问", "我想", "我要",
    "需要", "给我", "能不能", "可以", "吗", "呀", "呢", "啊",
}


class FastRouter:
    """快速规则路由器 —— 零 LLM 调用，毫秒级响应"""

    def route(self, question: str) -> Optional[FastRouteMatch]:
        """尝试规则匹配

        按优先级依次尝试所有规则，返回第一个匹配成功的结果。

        Args:
            question: 用户输入的问题

        Returns:
            匹配成功 → FastRouteMatch
            匹配失败 → None（降级到 Planner）
        """
        q = question.strip()

        # 优先级从高到低依次匹配（仅保留无需业务数据表的通用规则）
        rules = [
            ("greeting",   self._match_greeting),
            ("datetime",   self._match_datetime),
            ("calculator", self._match_calculator),
            ("weather",    self._match_weather),
            ("exchange",   self._match_exchange_rate),
        ]

        for rule_name, matcher in rules:
            result = matcher(q)
            if result is not None:
                logger.info(
                    f"FastRouter(规则) → 命中 [{rule_name}] → "
                    f"工具 [{result.tool_name}] is_final={result.is_final}"
                )
                return result

        logger.debug("FastRouter: 无匹配规则，降级到 Planner")
        return None

    def _match_weather_bare(self, q: str) -> Optional[FastRouteMatch]:
        '匹配不含城市名的天气查询',
        # 排除含明确城市名的查询
        city_patterns_2 = [
            r"(?:查询|查|看看|搜|搜索)\s*\w{2,4}\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度)",
            r"\w{2,4}\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度|天气\s*怎么样)",
        ]
        for pat in city_patterns_2:
            if re.search(pat, q):
                return None
        # 纯天气意图
        bare_patterns_2 = [
            r"天气\s*(?:怎么样|如何|好不好|好吗|预报)",
            r"(?:今天|明天|后天|这周)\s*(?:天气|气温|温度|冷不冷|热不热)",
            r"冷不冷|热不热|下雨吗|下雪吗|刮风吗",
            r"查\s*(?:天气|气温|温度|预报)",
            r"天气$",
        ]
        for pat in bare_patterns_2:
            if re.search(pat, q):
                return FastRouteMatch(
                    tool_name="weather",
                    tool_args={"city": "北京", "days": 1},
                    rule_name="weather_bare",
                    is_final=True,
                )
        return None

    # ────────────────── 各规则匹配器 ──────────────────

    def _match_weather(self, q: str) -> Optional[FastRouteMatch]:
        """匹配天气查询

        匹配模式：
          北京天气 / 查北京天气 / 北京今天天气
          上海气温 / 上海温度 / 上海天气怎么样
          明天杭州天气 / 后天北京天气
        """
        # 排除需要分析/推理的复杂查询（这些应交给 Agent 流程）
        analysis_patterns = [
            r'分析.*天气',
            r'天气.*适不适合',
            r'天气.*好不好',
            r'天气.*对.*影响',
            r'天气.*影响.*什么',
            r'天气.*适合.*(?:旅游|出行|运动|跑步)',
            r'天气.*对比',
            r'比较.*天气',
            r'推荐.*天气',
            r'天气.*建议',
            r'看.*天气.*怎么样',
        ]
        for pat in analysis_patterns:
            if re.search(pat, q):
                return None

        # 模式1：查询某地天气
        patterns = [
            # 模式1: "查询/查北京天气" / "查北京今天的天气"
            r'(?:查询|查|看看|搜|搜索)\s*((?:(?!今天|明天|后天|的)\w){2,4})\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度|的?气候)',
            # 模式2: "北京天气" / "东莞今天的天气" / "上海明天天气" / "深圳天气怎么样"
            r'((?:(?!今天|明天|后天|的)\w){2,4})\s*(?:今天|明天|后天)?\s*(?:的?天气|的?气温|的?温度|天气\s*怎么样|冷不冷|热不热|天气好吗)',
            # 模式3: "北京天气"/"北京的天气"/"北京今天天气"（紧凑格式，无空格分隔）
            r'((?:(?!今天|明天|后天|的)\w){2,4})(?:今天|明天|后天|的)(?:天气|气温|温度)',
        ]

        for pat in patterns:
            m = re.search(pat, q)
            if m:
                city = m.group(1)
                if city in _SKIP_WORDS:
                    continue

                # 智能判断查询天数
                days = 1
                if any(w in q for w in ["后天", "大后天"]):
                    days = 3
                elif any(w in q for w in ["明天"]):
                    days = 2
                elif any(w in q for w in ["一周", "7天", "未来几天"]):
                    days = 7
                # 如果提问包含"气温""温度"且没有时间词，也默认当天
                if any(w in q for w in ["这周", "本周", "一周天气"]):
                    days = 7

                return FastRouteMatch(
                    tool_name="weather",
                    tool_args={"city": city, "days": days},
                    rule_name="weather",
                    is_final=True,
                )

        return None

    # ────────────────── 问候 / 日期时间（零外部依赖）──────────────────

