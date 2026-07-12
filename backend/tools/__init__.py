"""
Tools Package —— AI Agent 工具系统

架构:
    Planner → ToolRouter (规则优先 → LLM function-calling)
            → ToolManager (注册中心 + 调度)
            → WeatherTool / MySQLTool / HttpTool / RAGTool / CalculatorTool

核心组件:
    - BaseTool: 工具抽象基类
    - ToolResult: 统一执行结果
    - ToolManager: 工具注册 & 执行调度
    - ToolRouter: 规则优先 + LLM 兜底工具选择
    - register_default_tools(): 一键注册所有默认工具

具体工具:
    - WeatherTool: 天气查询 (wttr.in)
    - MySQLTool: 数据库查询 (pymysql)
    - HttpTool: HTTP 请求
    - RAGTool: 知识库检索
    - CalculatorTool: 数学计算
"""
from tools.base_tool import BaseTool, ToolResult
from tools.tool_manager import ToolManager, get_tool_manager, register_default_tools
from tools.tool_router import ToolRouter

from tools.weather_tool import WeatherTool
from tools.mysql_tool import MySQLTool
from tools.http_tool import HttpTool
from tools.rag_tool import RAGTool
from tools.calculator_tool import CalculatorTool
from tools.datetime_tool import DateTimeTool
from tools.greeting_tool import GreetingTool

__all__ = [
    # 基础设施
    "BaseTool",
    "ToolResult",
    "ToolManager",
    "get_tool_manager",
    "register_default_tools",
    "ToolRouter",
    # 具体工具
    "WeatherTool",
    "MySQLTool",
    "HttpTool",
    "RAGTool",
    "CalculatorTool",
    "DateTimeTool",
    "GreetingTool",
]