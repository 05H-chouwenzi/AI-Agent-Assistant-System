"""
会话路由 —— 创建 & 列表 & 删除
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime

from database.session import get_db
from models.conversation import Conversation
from models.message import Message
from utils.auth import get_current_user
from models.user import User

router = APIRouter(prefix="/api/conversations", tags=["会话"])


# ============ Schema ============
class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    def serialize_created_at(self, v):
        return v.strftime("%Y-%m-%d %H:%M:%S") if v else None


# ============ 创建会话 ============
@router.post("/", response_model=ConversationResponse)
def create_conversation(
    req: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = Conversation(title=req.title, user_id=current_user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


# ============ 会话列表 ============
@router.get("/", response_model=list[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .all()
    )


# ============ 删除会话 ============
@router.delete("/{conv_id}")
def delete_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    conv.status = "archived"
    db.commit()
    return {"message": "已删除"}


# ============ 获取会话消息列表 ============
@router.get("/{conv_id}/messages")
def get_conversation_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个会话的所有消息"""
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "time": m.created_at.strftime("%H:%M") if m.created_at else "",
        }
        for m in messages
    ]
