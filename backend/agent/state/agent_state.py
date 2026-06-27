"""
Agent 状态定义 —— LangGraph State
"""
from typing import Optional
from typing_extensions import TypedDict

class AgentState(TypedDict):
    """工作流全局状态"""
    question:str
    task_type:Optional[str]
    retrieved_docs:Optional[list]
    tool_result:Optional[str]
    final_answer:Optional[str]