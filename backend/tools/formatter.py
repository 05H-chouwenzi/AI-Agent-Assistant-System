"""
Tool Result Formatter —— 将 ToolResult 转为用户友好的自然语言

用于 FastRouter 旁路的直接响应，跳过整个 Agent 流程。
每种工具类型有独立的格式化逻辑，避免 JSON 原始输出。
"""
from tools.base_tool import ToolResult


def format_tool_result(result: ToolResult, tool_name: str) -> str:
    """将 ToolResult 转为用户可读的文本"""
    if not result.success:
        return f"抱歉，{result.error or '工具执行失败'}"

    if tool_name == "greeting":
        return result.data.get("result", "你好！")

    if tool_name == "datetime":
        return result.data.get("result", str(result.data))

    if tool_name == "calculator":
        data = result.data if isinstance(result.data, dict) else {}
        expr = data.get("expression", "")
        val = data.get("result", "")
        if expr and val:
            return f"{expr} = {val}"
        return val if val else str(result.data)

    if tool_name == "weather":
        data = result.data if isinstance(result.data, dict) else {}
        lines = []
        if city := data.get("城市"):
            lines.append(f"📍 {city}")
        if cond := data.get("天气状况"):
            lines.append(f"🌤 天气：{cond}")
        if temp := data.get("当前温度"):
            lines.append(f"🌡 温度：{temp}")
        if feel := data.get("体感温度"):
            lines.append(f"🤗 体感：{feel}")
        if hum := data.get("湿度"):
            lines.append(f"💧 湿度：{hum}")
        if wind := data.get("风速"):
            lines.append(f"💨 风速：{wind}")
        if vis := data.get("能见度"):
            lines.append(f"👁 能见度：{vis}")

        # 未来预报
        if forecast := data.get("预报"):
            lines.append(f"\n📅 未来预报：")
            for day in forecast:
                date = day.get("日期", "")
                high = day.get("最高温", "")
                low = day.get("最低温", "")
                avg = day.get("平均温", "")
                parts = [f"  {date}"]
                if high:
                    parts.append(f"{high}")
                if low:
                    parts.append(f"{low}")
                if avg and avg not in (high, low):
                    parts.append(f"均{avg}")
                lines.append(" / ".join(parts))

        return "\n".join(lines) if lines else str(result.data)

    # 通用兜底：用 JSON 格式化
    import json
    data = result.data
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return str(data)
