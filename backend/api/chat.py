"""
聊天接口 —— 接收用户消息，调用 Agent 节点，返回结果
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.session import get_db
from models.message import Message
from models.conversation import Conversation
from models.user import User
from utils.auth import get_current_user
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from services.llm_service import call_llm
from logs.logger import log_agent_decision, log_final_answer

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


@router.post("/send", response_model=ChatResponse)
def chat_send(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户发送消息 → 节点处理 → 返回结果（非流式，带多轮记忆）"""

    # 加载历史消息
    history = []
    conv_id = req.conversation_id

    if conv_id and conv_id > 0:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        past_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        for m in past_messages:
            history.append({"role": m.role, "content": m.content})

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

        # 2. LLM 调用（图外处理，同步端点直接 call_llm）
        answer = call_llm(
            "你是一个专业的企业 AI 助手，请用中文回答。如用户问题涉及企业内部知识或需实时数据，结合参考信息回答。",
            state["prompt"],
            history=history[-10:],
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

    # === 记录日志 ===
    log_agent_decision(db, req.question, result.get("task_type", "unknown"))
    log_final_answer(db, req.question, result.get("final_answer", ""), elapsed_ms)

    # 保存消息到数据库
    if conv_id and conv_id > 0:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 保存用户消息
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=req.question,
        )
        db.add(user_msg)

        # 保存助手回复
        assistant_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=result.get("final_answer", ""),
        )
        db.add(assistant_msg)

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
    history = []
    conv_id = req.conversation_id

    if conv_id and conv_id > 0:
        conv = (
            db.query(Conversation)
            .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
            .first()
        )
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")

        past_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .all()
        )
        for m in past_messages:
            history.append({"role": m.role, "content": m.content})

    try:
        state: AgentState = {
            "question": req.question,
            "history": history[-10:],
            "user_id": current_user.id,
        }

        state = agent_graph.invoke(state)
        answer = call_llm("你是一个专业的企业 AI 助手，请用中文回答。如用户问题涉及企业内部知识或需实时数据，结合参考信息回答。", state["prompt"], history=history[-10:])

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

    return {
        "response": ChatResponse(
            question=result["question"],
            task_type=result.get("task_type", "unknown"),
            final_answer=result.get("final_answer", ""),
        ),
    }