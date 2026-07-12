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
  3. 订单查询    → MySQLTool（例："查询订单123"）
  4. 购物车查询  → MySQLTool（例："查看购物车"）
  5. 库存查询    → MySQLTool（例："查询库存"）
  6. 汇率查询    → HttpTool（例："美元汇率"）
  7. 股票查询    → HttpTool（例："查询股价"）
  注：自然语言数据库查询（如"查询所有用户"）走 Agent 流程，由 LLM 生成 SQL
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

        # 优先级从高到低依次匹配
        rules = [
            ("greeting",   self._match_greeting),
            ("datetime",   self._match_datetime),
            ("calculator", self._match_calculator),
            ("weather",    self._match_weather),
            ("stock",      self._match_stock),
            ("exchange",   self._match_exchange_rate),
            ("order",      self._match_order),
            ("cart",       self._match_cart),
            ("inventory",  self._match_inventory),
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

    def _match_greeting(self, q: str) -> Optional[FastRouteMatch]:
        """匹配问候语

        只匹配纯打招呼场景（短输入，无其他意图）：
          你好 / 您好 / 早上好 / 下午好 / 晚上好 / hi / hello
        如果问候后面还跟别的话（如"你好，查天气"），不匹配。
        """
        q_clean = q.strip().lower()

        pure_greetings = {
            "你好", "您好", "你好呀", "您好呀",
            "早上好", "下午好", "晚上好", "中午好",
            "hi", "hello", "hey",
        }
        # 去掉标点符号后比较
        q_stripped = re.sub(r'[，。！？、；：""''！@#￥%…&*（）【】,.\s]', '', q_clean)
        if q_stripped in pure_greetings:
            return FastRouteMatch(
                tool_name="greeting",
                tool_args={},
                rule_name="greeting",
                is_final=True,
            )

        return None

    def _match_datetime(self, q: str) -> Optional[FastRouteMatch]:
        """匹配日期/时间查询

        匹配模式：
          今天几号 / 今天星期几 / 现在几点 / 当前时间 / 什么日期
        """

        # 日期查询
        if re.search(r'今天\s*几号', q) or re.search(r'(?:当前|现在)\s*日期', q) or re.match(r'^日期$', q):
            return FastRouteMatch(
                tool_name="datetime",
                tool_args={"query_type": "date"},
                rule_name="datetime",
                is_final=True,
            )

        # 时间查询
        if (re.search(r'现在\s*几点', q) or re.search(r'当前\s*时间', q)
                or re.search(r'几点了', q) or re.match(r'^时间$', q)):
            return FastRouteMatch(
                tool_name="datetime",
                tool_args={"query_type": "time"},
                rule_name="datetime",
                is_final=True,
            )

        # 星期查询
        if (re.search(r'今天\s*星期[几天]', q) or re.search(r'今天\s*礼拜[几天]', q)
                or re.match(r'^星期$', q) or re.match(r'^礼拜$', q)):
            return FastRouteMatch(
                tool_name="datetime",
                tool_args={"query_type": "weekday"},
                rule_name="datetime",
                is_final=True,
            )

        # 兜底：包含"今天日期"、"今天时间"之类的混合查询
        if re.search(r'今天.*(?:日期|时间)', q):
            return FastRouteMatch(
                tool_name="datetime",
                tool_args={"query_type": "datetime"},
                rule_name="datetime",
                is_final=True,
            )

        return None

    def _match_calculator(self, q: str) -> Optional[FastRouteMatch]:
        """匹配数学计算

        匹配模式：
          计算 123+456
          123+456
          sqrt(64)
          2*8+6/2
          (1+2)*3
        """
        q_clean = q.strip()

        # 模式1：以"计算"开头
        m = re.search(r'(?:计算|算一下|帮我算)\s*([\d+\-*/%.()\s²√πeE]+)', q_clean)
        if m:
            expr = m.group(1).strip()
            expr = expr.replace('²', '**2').replace('√', 'sqrt ')
            expr = expr.replace('×', '*').replace('÷', '/')
            return FastRouteMatch(
                tool_name="calculator",
                tool_args={"expression": expr},
                rule_name="calculator",
                is_final=True,
            )

        # 模式2：纯数学表达式（只含数字、运算符、括号、小数点）
        pure_math = re.match(
            r'^[\d+\-*/%.()\s²√πeEx10^]+$', q_clean, re.IGNORECASE
        )
        if pure_math and re.search(r'[\+\-\*/^]', q_clean):
            expr = q_clean.strip()
            expr = expr.replace('²', '**2').replace('√', 'sqrt ')
            expr = expr.replace('×', '*').replace('÷', '/')
            expr = expr.replace('^', '**')
            return FastRouteMatch(
                tool_name="calculator",
                tool_args={"expression": expr},
                rule_name="calculator",
                is_final=True,
            )

        # 模式3：数学函数表达式 sqrt/sin/cos/tan/log
        m = re.match(
            r'^(sqrt|sin|cos|tan|log|ln|abs|pow|ceil|floor|round|max|min)\s*\('
            r'[\d,.\s]+\s*\)$',
            q_clean, re.IGNORECASE
        )
        if m:
            return FastRouteMatch(
                tool_name="calculator",
                tool_args={"expression": q_clean},
                rule_name="calculator",
                is_final=True,
            )

        return None

    def _match_stock(self, q: str) -> Optional[FastRouteMatch]:
        """匹配股票/股价查询

        匹配模式：
          查询xxx股票
          xxx股价
          xxx行情
        """
        patterns = [
            r'(?:查询|查|看看)\s*(\w+)\s*(?:的?股票|的?股价|的?行情)',
            r'(\w{2,6})\s*(?:股票|股价|行情)(?:\s*怎么样|\s*多少)?',
        ]
        for pat in patterns:
            m = re.search(pat, q)
            if m:
                stock = m.group(1)
                if stock in _SKIP_WORDS:
                    continue
                return FastRouteMatch(
                    tool_name="http",
                    tool_args={
                        "url": f"https://api.example.com/stock/{stock}",
                        "method": "GET",
                    },
                    rule_name="stock",
                    is_final=False,
                )
        return None

    def _match_exchange_rate(self, q: str) -> Optional[FastRouteMatch]:
        """匹配汇率查询

        匹配模式：
          美元汇率 / 美金汇率 / 欧元汇率
          美元兑人民币
          查汇率
        """
        currencies = r'(?:美元|美金|欧元|英镑|日元|港币|韩元|泰铢|卢布|加元|澳元|新加坡元|人民币)'

        # 模式1：单一货币汇率查询
        if re.search(rf'^{currencies}?\s*(?:汇率|牌价)', q):
            return FastRouteMatch(
                tool_name="http",
                tool_args={
                    "url": "https://api.exchangerate-api.com/v4/latest/CNY",
                    "method": "GET",
                },
                rule_name="exchange_rate",
                is_final=True,
            )

        # 模式2：兑换查询
        m = re.search(rf'({currencies})\s*(?:兑|对|换)\s*({currencies})', q)
        if m:
            return FastRouteMatch(
                tool_name="http",
                tool_args={
                    "url": f"https://api.exchangerate-api.com/v4/latest/CNY",
                    "method": "GET",
                },
                rule_name="exchange_rate",
                is_final=True,
            )

        # 模式3：直接问"汇率"
        if re.match(r'^查询?\s*(?:汇率|牌价|外汇)|[?？]?$', q):
            return FastRouteMatch(
                tool_name="http",
                tool_args={
                    "url": "https://api.exchangerate-api.com/v4/latest/CNY",
                    "method": "GET",
                },
                rule_name="exchange_rate",
                is_final=True,
            )

        return None

    def _match_order(self, q: str) -> Optional[FastRouteMatch]:
        """匹配订单查询

        匹配模式：
          查询订单123
          查订单号2024001
          查看所有订单
          我的历史订单
        """
        # 查询指定订单
        m = re.search(r'(?:查询|查|找|搜索)\s*(?:订单|订|单号|订单号)\s*(\w+)', q)
        if m:
            order_id = m.group(1)
            return FastRouteMatch(
                tool_name="mysql",
                tool_args={
                    "query": f"SELECT * FROM orders WHERE order_id = '{order_id}' LIMIT 1",
                    "limit": 1,
                },
                rule_name="order",
                is_final=True,
            )

        # 查询订单列表
        if re.search(r'(?:查看|查询|我的|所有|历史)\s*(?:所有订单|订单列表|历史订单|全部订单)', q):
            return FastRouteMatch(
                tool_name="mysql",
                tool_args={
                    "query": "SELECT * FROM orders ORDER BY created_at DESC LIMIT 10",
                    "limit": 10,
                },
                rule_name="order",
                is_final=True,
            )

        return None

    def _match_cart(self, q: str) -> Optional[FastRouteMatch]:
        """匹配购物车查询

        匹配模式：
          查看购物车
          我的购物车
        """
        if re.search(r'(?:查看|查询|我的)\s*购物车', q):
            return FastRouteMatch(
                tool_name="mysql",
                tool_args={
                    "query": (
                        "SELECT sc.id, sc.quantity, p.name, p.price "
                        "FROM shopping_cart_items sc "
                        "JOIN products p ON sc.product_id = p.id "
                        "LIMIT 20"
                    ),
                    "limit": 20,
                },
                rule_name="cart",
                is_final=True,
            )

        return None

    def _match_inventory(self, q: str) -> Optional[FastRouteMatch]:
        """匹配库存查询

        匹配模式：
          查询库存
          查存货
          查询xxx库存
        """
        m = re.search(r'(?:查询|查|看看)\s*(?:库存|存货|存量)\s*(\w*)', q)
        if m:
            product = m.group(1).strip() if m.lastindex else ""
            if product:
                query = f"SELECT * FROM inventory WHERE product_name LIKE '%{product}%' LIMIT 10"
            else:
                query = "SELECT * FROM inventory LIMIT 10"
            return FastRouteMatch(
                tool_name="mysql",
                tool_args={"query": query, "limit": 10},
                rule_name="inventory",
                is_final=True,
            )

        return None

    # data_query 规则已移除（自然语言查询由 Agent 流程的 LLM 处理，
    # FastRouter 无法将自然语言可靠地转为 SQL，
    # 直接传原文给 MySQL 工具必然失败）
