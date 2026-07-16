"""Agent State —— 循环图的全局状态定义

完全匹配 ai-agent 架构，使用 LangChain BaseMessage 管理对话消息。
"""
from operator import add
from typing import Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Agent 工作流状态 —— 匹配 ai-agent 架构

    使用 LangChain BaseMessage 管理对话消息，支持 add_messages 归约。
    """
    messages: Annotated[list[BaseMessage], add_messages]
    tenant_id: int
    user_id: int
    next_agent: str                          # "research" | "data" | "general" | "FINISH"
    route_history: Annotated[list[str], add]  # 已执行过的 Agent 列表
    step_count: int                           # 当前步数
    last_worker: str                          # 上一个执行的 Worker
