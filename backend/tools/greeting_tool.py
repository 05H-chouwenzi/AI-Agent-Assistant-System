"""
Greeting Tool —— 问候语工具（零外部依赖）

根据当前时间返回合适的问候语：
  早上（5-12点）→ 早上好
  下午（12-18点）→ 下午好
  晚上（18-22点）→ 晚上好
  深夜（22-5点）→ 夜深了/你好
"""
from datetime import datetime
from tools.base_tool import BaseTool, ToolResult


class GreetingTool(BaseTool):

    @property
    def name(self) -> str:
        return "greeting"

    @property
    def description(self) -> str:
        return "返回问候语。适用于用户打招呼的场景，如'你好'、'早上好'等。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "greeting_type": {
                    "type": "string",
                    "description": "问候类型，留空自动根据时间判断",
                    "enum": ["morning", "afternoon", "evening", "general"],
                }
            },
        }

    def execute(self, **kwargs) -> ToolResult:
        hour = datetime.now().hour

        # 根据时间自动选择问候语
        if 5 <= hour < 12:
            msg = "早上好！有什么可以帮您的吗？☀️"
        elif 12 <= hour < 14:
            msg = "中午好！有什么可以帮您的吗？🌞"
        elif 14 <= hour < 18:
            msg = "下午好！有什么可以帮您的吗？🌤"
        elif 18 <= hour < 22:
            msg = "晚上好！有什么可以帮您的吗？🌙"
        else:
            msg = "夜深了，注意休息哦！有什么可以帮您的吗？🌟"

        return ToolResult(
            success=True,
            data={"result": msg},
            tool_name=self.name,
        )
