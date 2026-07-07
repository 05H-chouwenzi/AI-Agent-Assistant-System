"""
聊天接口 —— 接收用户消息，调用 Agent 节点，返回结果
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from services.llm_service import call_llm
from logs.operation_logger import OperationLogger, Actions
from tools.tool_manager import get_tool_manager
from crud import conversation as conv_crud
from crud import message as msg_crud

router = APIRouter(prefix="/api/chat", tags=["聊天"])


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    conversation_id: int = 0


class ChatResponse(BaseModel):
    """聊天响应"""
    question: str
    task_type: str
    final_answer: str


def _load_history(db: Session, conv_id: int, user_id: int) -> list:
    """加载会话历史消息"""
    history = []
    if conv_id and conv_id > 0:
        conv = conv_crud.get_conversation(db, conv_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        past_messages = msg_crud.get_conversation_messages(db, conv_id)
        for m in past_messages:
            history.append({"role": m.role, "content": m.content})
    return history


@router.post("/send", response_model=ChatResponse)
def chat_send(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户发送消息 → 节点处理 → 返回结果（非流式，带多轮记忆）"""

    # 加载历史消息
    history = _load_history(db, req.conversation_id, current_user.id)

    start = time.time()

    # 使用直接节点调用（替代原 LangGraph Workflow）
    try:
        state: AgentState = {
            "question": req.question,
            "history": history[-10:],
            "user_id": current_user.id,
        }

        # 1. LangGraph Workflow：planner → (rag/tool) → prompt_builder
        state = agent_graph.invoke(state)

        # 2. LLM 调用（图外处理，同步端点直接 call_llm，附带工具定义）
        tool_manager = get_tool_manager()
        tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None

        answer = call_llm(
            "你是一个专业的企业 AI 助手，请用中文回答。你可以使用工具中心的工具（天气查询、数据库查询、HTTP请求、知识库检索等）来获取实时数据。如果用户需要查询天气等实时信息，优先使用相关工具。",
            state["prompt"],
            history=history[-10:],
            tools=tool_schemas,
        )

        result = {
            "question": req.question,
            "task_type": state.get("task_type", "direct"),
            "final_answer": answer,
        }
    except Exception as e:
        result = {
            "question": req.question,
            "task_type": "error",
            "final_answer": f"系统错误：{str(e)}",
        }

    elapsed_ms = (time.time() - start) * 1000

    # === 记录操作日志（分类：chat.ask）===
    OperationLogger.log_chat_question(
        db,
        user_id=current_user.id,
        question=req.question,
        task_type=result.get("task_type", "unknown"),
        is_stream=False,
        conversation_id=req.conversation_id or None,
        elapsed_ms=int(elapsed_ms),
        answer=result.get("final_answer", ""),
    )

    # 保存消息到数据库
    if req.conversation_id and req.conversation_id > 0:
        conv_id = req.conversation_id
        conv = conv_crud.get_conversation(db, conv_id, current_user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        msg_crud.create_message(db, conv_id, "user", req.question)
        msg_crud.create_message(db, conv_id, "assistant", result.get("final_answer", ""))
        db.commit()

    return ChatResponse(
        question=result["question"],
        task_type=result.get("task_type", "unknown"),
        final_answer=result.get("final_answer", "抱歉，我无法回答这个问题"),
    )


@router.post("/send-with-trace")
def chat_send_with_trace(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    用户发送消息 → Agent 处理 → 返回结果（不含追踪）
    （该端点沿用 /send 的实现，如需调试信息请查看服务端日志）
    """

    # 加载历史消息
    history = _load_history(db, req.conversation_id, current_user.id)
    conv_id = req.conversation_id

    start = time.time()
    try:
        state: AgentState = {
            "question": req.question,
            "history": history[-10:],
            "user_id": current_user.id,
        }

        state = agent_graph.invoke(state)
        tool_manager = get_tool_manager()
        tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None
        answer = call_llm("你是一个专业的企业 AI 助手，请用中文回答。你可以使用工具中心的工具（天气查询、数据库查询、HTTP请求、知识库检索等）来获取实时数据。如果用户需要查询天气等实时信息，优先使用相关工具。", state["prompt"], history=history[-10:], tools=tool_schemas)

        result = {
            "question": req.question,
            "task_type": state.get("task_type", "direct"),
            "final_answer": answer,
        }
    except Exception as e:
        result = {
            "question": req.question,
            "task_type": "error",
            "final_answer": f"系统错误：{str(e)}",
        }

    elapsed_ms = (time.time() - start) * 1000

    # ★ 记录操作日志
    OperationLogger.log_chat_question(
        db,
        user_id=current_user.id,
        question=req.question,
        task_type=result.get("task_type", "unknown"),
        is_stream=False,
        conversation_id=conv_id or None,
        elapsed_ms=int(elapsed_ms),
        answer=result.get("final_answer", ""),
    )

    return {
        "response": ChatResponse(
            question=result["question"],
            task_type=result.get("task_type", "unknown"),
            final_answer=result.get("final_answer", ""),
        ),
    }