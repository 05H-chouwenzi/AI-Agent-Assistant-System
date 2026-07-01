"""
Agent 状态定义 —— LangGraph State（支持多工具调用）
"""
from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict


class ToolCallRecord(TypedDict, total=False):
    """单次工具调用记录"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]]     # ToolResult.to_dict()
    success: bool
    error: Optional[str]
    execution_time_ms: float


class AgentState(TypedDict, total=False):
    """工作流全局状态"""
    question: str
    history: Optional[List[dict]]        # [{"role":"user"/"assistant", "content":"..."}]
    task_type: Optional[str]             # "rag" | "tool" | "direct"
    user_id: Optional[int]               # 当前用户ID，用于知识库隔离
    retrieved_docs: Optional[list]
    tool_result: Optional[str]           # 兼容旧格式：工具的文本结果
    tool_calls: Optional[List[ToolCallRecord]]   # 新格式：结构化工具调用记录
    tool_results: Optional[List[Dict[str, Any]]]  # 新格式：工具返回的结构化结果
    prompt: Optional[str]                # 构建好的 LLM 提示词（由 graph 生成，API 层消费）
    final_answer: Optional[str]