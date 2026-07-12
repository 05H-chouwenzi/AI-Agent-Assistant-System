"""
DateTime Tool —— 日期时间查询工具（零外部依赖）

功能：
  - 获取当前日期：2026年7月12日
  - 获取当前时间：14:30:00
  - 获取星期几：星期日
  - 组合返回：2026年7月12日 14:30:00，星期日

不需要调任何外部 API，直接从系统获取。
"""
from datetime import datetime
from typing import Any
from tools.base_tool import BaseTool, ToolResult


class DateTimeTool(BaseTool):

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return "获取当前日期和时间。适用于查询今天的日期、当前时间、星期几等场景。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "查询类型: date(日期), time(时间), datetime(完整日期时间), weekday(星期几)",
                    "enum": ["date", "time", "datetime", "weekday"],
                }
            },
            "required": ["query_type"],
        }

    def execute(self, **kwargs) -> ToolResult:
        query_type = kwargs.get("query_type", "datetime")
        now = datetime.now()

        weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

        if query_type == "date":
            result = now.strftime("%Y年%m月%d日")
        elif query_type == "time":
            result = now.strftime("%H:%M:%S")
        elif query_type == "weekday":
            result = weekday_names[now.weekday()]
        else:
            result = (
                f"{now.strftime('%Y年%m月%d日')} "
                f"{now.strftime('%H:%M:%S')}，"
                f"{weekday_names[now.weekday()]}"
            )

        return ToolResult(
            success=True,
            data={"result": result},
            tool_name=self.name,
        )
