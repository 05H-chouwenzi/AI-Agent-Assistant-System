"""
LangChain 工具适配器 —— 将现有工具包装为 LangChain BaseTool

供 create_react_agent 使用，让 Worker Agent 能调用现有工具系统。
"""
import asyncio
from typing import Any, Optional, Type
from langchain_core.tools import BaseTool as LCBaseTool
from pydantic import BaseModel, Field, create_model

from tools.tool_manager import get_tool_manager


def _create_langchain_tool(tool_name: str) -> Optional[LCBaseTool]:
    """将现有工具包装为 LangChain BaseTool

    Args:
        tool_name: 工具名称（如 "weather", "rag_search", "mysql" 等）
    Returns:
        LangChain BaseTool 实例，如果工具不存在则返回 None
    """
    manager = get_tool_manager()
    tool = manager.get(tool_name)
    if tool is None:
        return None

    # 从现有工具的 parameters 动态构建 Pydantic 输入模型
    params_schema = tool.parameters
    props = params_schema.get("properties", {})
    required_fields = set(params_schema.get("required", []))

    # 使用 create_model 正确创建 Pydantic v2 模型
    field_definitions = {}
    for prop_name, prop_info in props.items():
        field_type = _json_type_to_python(prop_info.get("type", "string"))
        desc = prop_info.get("description", "")
        if prop_name in required_fields:
            field_definitions[prop_name] = (field_type, Field(..., description=desc))
        else:
            default = prop_info.get("default", None)
            field_definitions[prop_name] = (Optional[field_type], Field(default=default, description=desc))

    InputModel = create_model(
        f"{tool_name.capitalize()}Input",
        **field_definitions,
    )

    class LangChainTool(LCBaseTool):
        """LangChain 工具包装器"""
        name: str = tool_name
        description: str = tool.description
        args_schema: Type[BaseModel] = InputModel

        def _run(self, **kwargs) -> Any:
            result = manager.execute(tool_name, **kwargs)
            return result.to_dict() if result.success else {"error": result.error}

        async def _arun(self, **kwargs) -> Any:
            # 优先使用工具的异步执行方法（真正不阻塞事件循环）
            if hasattr(manager, "aexecute"):
                result = await manager.aexecute(tool_name, **kwargs)
                return result.to_dict() if result.success else {"error": result.error}
            # 兜底：将同步执行放入线程池，避免阻塞事件循环
            result = await asyncio.to_thread(manager.execute, tool_name, **kwargs)
            return result.to_dict() if result.success else {"error": result.error}

    return LangChainTool()


def _json_type_to_python(json_type: str) -> type:
    """JSON Schema 类型 → Python 类型映射"""
    mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return mapping.get(json_type, str)


def get_research_tools(tenant_id: Any = None) -> list[LCBaseTool]:
    """获取 Research Agent 可用工具"""
    tools = []
    t = _create_langchain_tool("rag_search")
    if t:
        tools.append(t)
    return tools


def get_data_tools(tenant_id: Any = None) -> list[LCBaseTool]:
    """获取 Data Agent 可用工具"""
    tools = []
    t = _create_langchain_tool("mysql")
    if t:
        tools.append(t)
    return tools


def get_general_tools() -> list[LCBaseTool]:
    """获取 General Agent 可用工具"""
    tools = []
    for name in ["weather", "calculator", "datetime", "greeting", "http"]:
        t = _create_langchain_tool(name)
        if t:
            tools.append(t)
    return tools
