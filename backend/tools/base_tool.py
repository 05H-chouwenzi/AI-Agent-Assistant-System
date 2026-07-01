"""
Base Tool —— 所有工具的抽象基类 & 统一返回结构
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass
import datetime
from decimal import Decimal


def _json_safe(obj):
    """递归将 datetime/date/Decimal 等非 JSON 可序列化类型转为字符串（全局统一）"""
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(i) for i in obj]
    return obj


@dataclass
class ToolResult:
    """标准化的工具执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    tool_name: str = ""
    execution_time_ms: float = 0.0

    def to_message(self) -> str:
        """转为 LLM 可读的文本"""
        if self.success:
            if isinstance(self.data, (dict, list)):
                import json
                return json.dumps(self.data, ensure_ascii=False, indent=2, default=str)
            return str(self.data)
        return f"工具 [{self.tool_name}] 执行失败: {self.error}"

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": _json_safe(self.data),
            "error": self.error,
            "tool_name": self.tool_name,
            "execution_time_ms": self.execution_time_ms,
        }


class BaseTool(ABC):
    """
    工具基类 —— 所有工具必须继承此类

    子类需实现:
        name          -> 工具唯一标识
        description   -> 工具描述（给 LLM 看）
        parameters    -> 参数 JSON Schema（OpenAI function calling 格式）
        execute(**kwargs) -> 执行逻辑，返回 ToolResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识，如 'weather', 'mysql', 'http'"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述，LLM 据此决定是否选用此工具"""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """
        参数 JSON Schema（OpenAI function calling 格式）
        示例:
        {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称"}
            },
            "required": ["city"]
        }
        """
        ...

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """执行工具逻辑，返回 ToolResult"""
        ...

    def to_function_schema(self) -> dict:
        """转为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name!r})>"
