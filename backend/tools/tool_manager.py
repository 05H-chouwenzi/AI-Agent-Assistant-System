"""
Tool Manager —— 工具注册中心 & 执行调度器

职责:
1. 注册/注销工具
2. 按名称查找工具
3. 列出所有可用工具
4. 收集所有 tools 的 function schema（给 LLM function calling 用）
5. 执行指定工具并统一返回 ToolResult
"""
import time
from typing import Dict, List, Optional
from tools.base_tool import BaseTool, ToolResult
from logs.logger import logger


class ToolManager:
    """工具管理器 —— 单例模式"""

    _instance: Optional["ToolManager"] = None

    def __new__(cls) -> "ToolManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: Dict[str, BaseTool] = {}
            cls._instance._initialized = False
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """注册一个工具"""
        if tool.name in self._tools:
            logger.warning(f"工具 [{tool.name}] 已存在，将被覆盖")
        self._tools[tool.name] = tool
        logger.info(f"工具已注册: {tool.name} ({tool.__class__.__name__})")

    def register_many(self, tools: List[BaseTool]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> bool:
        """注销工具，返回是否成功"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"工具已注销: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[BaseTool]:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_names(self) -> List[str]:
        """列出所有已注册的工具名称"""
        return sorted(self._tools.keys())

    def list_tools(self) -> List[BaseTool]:
        """列出所有已注册的工具实例"""
        return list(self._tools.values())

    def get_function_schemas(self) -> List[dict]:
        """获取所有工具的 function schema（OpenAI function calling 格式）"""
        return [tool.to_function_schema() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """获取人类可读的工具列表"""
        lines = []
        for tool in self._tools.values():
            lines.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(lines)

    def execute(self, name: str, **kwargs) -> ToolResult:
        """执行指定工具"""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                error=f"工具 [{name}] 未注册。可用工具: {', '.join(self.list_names())}",
                tool_name=name,
            )

        logger.info(f"执行工具: {name}, 参数: {kwargs}")
        start = time.time()
        try:
            result = tool.execute(**kwargs)
            result.tool_name = name
            elapsed = (time.time() - start) * 1000
            if result.execution_time_ms == 0:
                result.execution_time_ms = round(elapsed, 2)
            logger.info(f"工具 [{name}] 执行{'成功' if result.success else '失败'} ({result.execution_time_ms}ms)")
            return result
        except Exception as e:
            logger.error(f"工具 [{name}] 执行异常: {str(e)}")
            return ToolResult(
                success=False,
                error=f"工具执行异常: {str(e)}",
                tool_name=name,
            )

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def is_empty(self) -> bool:
        return len(self._tools) == 0


# ==================== 全局便捷函数 ====================

def get_tool_manager() -> ToolManager:
    """获取全局 ToolManager 实例"""
    return ToolManager()


def register_default_tools(manager: Optional[ToolManager] = None) -> ToolManager:
    """
    注册所有默认工具到 ToolManager

    调用一次即可，后续直接使用 get_tool_manager() 获取
    """
    if manager is None:
        manager = get_tool_manager()

    # 只在首次调用时注册
    if manager._initialized:
        return manager

    from tools.weather_tool import WeatherTool
    from tools.mysql_tool import MySQLTool
    from tools.http_tool import HttpTool
    from tools.rag_tool import RAGTool
    from tools.calculator_tool import CalculatorTool
    from tools.datetime_tool import DateTimeTool
    from tools.greeting_tool import GreetingTool

    manager.register_many([
        WeatherTool(),
        MySQLTool(),
        HttpTool(),
        RAGTool(),
        CalculatorTool(),
        DateTimeTool(),
        GreetingTool(),
    ])

    manager._initialized = True
    logger.info(f"默认工具注册完成，共 {manager.tool_count} 个工具")
    return manager
