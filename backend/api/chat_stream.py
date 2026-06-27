"""
聊天流式接口 —— SSE 逐字推送 + 保存聊天历史到 MySQL
"""
import json
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.session import SessionLocal
from models.conversation import Conversation
from models.message import Message
from models.user import User
from utils.auth import get_current_user
from agent.state.agent_state import AgentState
from agent.nodes.planner import planner_node
from agent.nodes.llm_node import build_prompt
from services.llm_service import stream_llm

router = APIRouter(prefix="/api/chat", tags=["聊天"])


class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0


@router.post("/stream")
def chat_stream(req: ChatStreamRequest, user: User = Depends(get_current_user)):
    """流式：Planner → LLM → SSE 逐字返回 + 保存消息"""

    async def event_stream():
        db = SessionLocal()
        try:
            # 0. 如果 conv_id=0 则自动创建新会话
            conv_id = req.conversation_id
            if not conv_id or conv_id == 0:
                conv = Conversation(title=req.question[:30], user_id=user.id)
                db.add(conv)
                db.commit()
                db.refresh(conv)
                conv_id = conv.id

            state: AgentState = {"question": req.question}

            # 1. 保存用户消息
            user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
            db.add(user_msg)
            db.commit()

            # 2. Planner
            state = planner_node(state)
            yield f"data: {json.dumps({'type': 'meta', 'task_type': state['task_type']}, ensure_ascii=False)}\n\n"

            # 3. 构建 prompt → 流式调 LLM
            prompt = build_prompt(state)
            full = ""
            for chunk in stream_llm("你是一个专业的企业 AI 助手，请用中文回答。", prompt):
                full += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # 4. 保存 AI 回答
            ai_msg = Message(conversation_id=conv_id, role="assistant", content=full)
            db.add(ai_msg)
            db.commit()

            # 5. 对话标题自动设为第一句用户问题
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if conv and conv.title == "新对话":
                conv.title = req.question[:30]
                db.commit()

            yield f"data: {json.dumps({'type': 'done', 'content': full, 'message_id': ai_msg.id, 'conversation_id': conv_id}, ensure_ascii=False)}\n\n"

        finally:
            db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
