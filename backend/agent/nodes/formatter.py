"""
Formatter —— 工具结果格式化器

职责：
  工具执行完成后，将结构化结果格式化为用户可直接阅读的文本。
  替代 LLM 组织回答的步骤，大幅降低响应时间。

用法：
  from agent.nodes.formatter import Formatter

  formatter = Formatter()
  display_text = formatter.format(tool_name, tool_result)

输出示例：

  天气：
  📍 北京
  🌤 晴  25°C（体感 26°C）
  💧 60%  🌬 15 km/h 南风

  计算：
  🔢 123 + 456 = 579

  数据库：
  📊 共 3 条记录
  1. order_id | amount | status
  2. 1001     | 200    | 已发货
  3. 1002     | 350    | 待付款
"""
from typing import Any, Dict, List, Union
from tools.base_tool import ToolResult
from logs.logger import logger


class Formatter:
    """工具结果格式化器 —— 代码格式化，不调用 LLM"""

    def format(self, tool_name: str, result: ToolResult) -> str:
        """格式化工具结果为显示文本

        Args:
            tool_name: 工具名称
            result: 工具执行结果

        Returns:
            格式化好的用户可读文本
        """
        if not result.success:
            error_msg = result.error or "未知错误"
            logger.warning(f"Formatter: 工具 [{tool_name}] 执行失败: {error_msg}")
            return f"❌ {error_msg}"

        # 按工具类型分发格式化
        formatter_fn = getattr(self, f"_format_{tool_name}", self._format_default)
        try:
            formatted = formatter_fn(result.data)
            logger.debug(f"Formatter: [{tool_name}] 格式化成功 ({len(formatted)} chars)")
            return formatted
        except Exception as e:
            logger.error(f"Formatter: [{tool_name}] 格式化异常: {e}")
            return self._format_default(result.data)

    # ────────────────── 各工具专用格式化器 ──────────────────

    def _format_greeting(self, data: dict) -> str:
        """格式化问候语"""
        return data.get("result", "你好！有什么可以帮您的吗？")

    def _format_datetime(self, data: dict) -> str:
        """格式化日期时间"""
        return f"🕐 {data.get('result', '')}"

    def _format_weather(self, data: dict) -> str:
        """格式化天气数据为可读文本"""
        lines = [f"📍 {data.get('城市', '未知城市')}"]

        weather = data.get('天气状况', 'N/A')
        temp = data.get('当前温度', 'N/A')
        feel = data.get('体感温度', 'N/A')
        lines.append(f"🌤  {weather}  {temp}（体感 {feel}）")

        humidity = data.get('湿度', 'N/A')
        wind_speed = data.get('风速', 'N/A')
        wind_dir = data.get('风向', '')
        if wind_dir:
            lines.append(f"💧 {humidity}  🌬 {wind_speed} {wind_dir}")
        else:
            lines.append(f"💧 {humidity}  🌬 {wind_speed}")

        if data.get('能见度') and data['能见度'] != 'N/A':
            lines.append(f"👁 能见度: {data['能见度']}")

        uv = data.get('紫外线指数', 'N/A')
        if uv != 'N/A':
            lines.append(f"☀️ 紫外线指数: {uv}")

        # 天气预报
        forecasts = data.get('预报')
        if forecasts:
            lines.append("")
            for f in forecasts:
                date = f.get('日期', '')
                lines.append(f"📅 {date}")
                lines.append(
                    f"  最高 {f.get('最高温', 'N/A')} / "
                    f"最低 {f.get('最低温', 'N/A')} / "
                    f"平均 {f.get('平均温', 'N/A')}"
                )

        return "\n".join(lines)

    def _format_calculator(self, data: dict) -> str:
        """格式化计算结果"""
        expr = data.get("expression", "")
        result = data.get("result", "")
        return f"🔢 {expr} = {result}"

    def _format_mysql(self, data: Any) -> str:
        """格式化 MySQL 数据库查询结果"""
        if isinstance(data, dict):
            # 兼容旧格式：{"查询": "...", "结果": [...]}
            raw_rows = data.get("结果", data.get("rows", data.get("data", [])))
            query = data.get("查询", data.get("query", ""))
        elif isinstance(data, list):
            raw_rows = data
            query = ""
        else:
            return self._format_default(data)

        if not raw_rows or not isinstance(raw_rows, list):
            return "📭 未找到匹配的记录"

        # 推断列名
        first = raw_rows[0]
        if isinstance(first, dict):
            headers = list(first.keys())
            rows = [[row.get(h, "") for h in headers] for row in raw_rows]
        elif isinstance(first, (list, tuple)):
            rows = [[str(item) for item in row] for row in raw_rows]
        else:
            rows = [[str(item) for item in raw_rows]]

        lines = [f"📊 共 {len(raw_rows)} 条记录"]
        if query:
            lines.append(f"🔍 {query[:80]}")

        for i, row in enumerate(rows, 1):
            lines.append(f"{i}. {' | '.join(str(c) for c in row)}")

        return "\n".join(lines)

    def _format_http(self, data: Any) -> str:
        """格式化 HTTP 请求结果"""
        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    import json
                    lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:200]}")
                else:
                    lines.append(f"{k}: {v}")
            return "\n".join(lines)
        return str(data)

    def _format_rag_search(self, data: Any) -> str:
        """格式化知识库搜索结果"""
        if isinstance(data, dict):
            results = data.get("results", data.get("data", []))
        elif isinstance(data, list):
            results = data
        else:
            return str(data)

        if not results or not isinstance(results, list):
            return "📭 未找到相关知识"

        lines = [f"📚 找到 {len(results)} 条相关结果\n"]
        for i, doc in enumerate(results, 1):
            if isinstance(doc, dict):
                content = doc.get("content", doc.get("text", str(doc)[:200]))
                source = doc.get("source", "")
                score = doc.get("score", "")
                lines.append(f"{i}. {str(content)[:200]}")
                if source:
                    lines.append(f"   来源: {source}")
                if score:
                    lines.append(f"   相关度: {score}")
            else:
                lines.append(f"{i}. {str(doc)[:200]}")

        return "\n".join(lines)

    # ────────────────── 兜底格式化器 ──────────────────

    def _format_default(self, data: Any) -> str:
        """默认格式化器 —— 适用于没有专用格式化的工具"""
        if isinstance(data, dict):
            return "\n".join(f"{k}: {v}" for k, v in data.items())
        if isinstance(data, list):
            if not data:
                return "（空）"
            lines = []
            for i, item in enumerate(data, 1):
                if isinstance(item, (dict, list)):
                    import json
                    lines.append(f"{i}. {json.dumps(item, ensure_ascii=False)[:200]}")
                else:
                    lines.append(f"{i}. {item}")
            return "\n".join(lines)
        return str(data)
