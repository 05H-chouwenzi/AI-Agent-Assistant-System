"""
会话路由 —— 创建 & 列表 & 删除
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_serializer
from typing import Optional
from datetime import datetime

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from logs.operation_logger import OperationLogger, Actions
from crud import conversation as conv_crud
from crud import message as msg_crud

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
    conv = conv_crud.create_conversation(db, req.title, current_user.id)

    # ★ 记录操作日志
    OperationLogger.log_conversation_event(
        db,
        action=Actions.CONVERSATION_CREATE,
        user_id=current_user.id,
        conv_title=conv.title,
        conv_id=conv.id,
        detail={"title": conv.title},
    )

    return conv


# ============ 会话列表 ============
@router.get("/", response_model=list[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convs = conv_crud.get_user_active_conversations(db, current_user.id)

    # ★ 记录操作日志
    OperationLogger.log_conversation_event(
        db,
        action=Actions.CONVERSATION_LIST,
        user_id=current_user.id,
        conv_title=f"会话列表(共{len(convs)}个)",
        detail={"count": len(convs)},
    )

    return convs


# ============ 删除会话 ============
@router.delete("/{conv_id}")
def delete_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = conv_crud.archive_conversation(db, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    # ★ 记录操作日志
    OperationLogger.log_conversation_event(
        db,
        action=Actions.CONVERSATION_DELETE,
        user_id=current_user.id,
        conv_title=conv.title,
        conv_id=conv_id,
    )

    return {"message": "已删除"}


# ============ 获取会话消息列表 ============
@router.get("/{conv_id}/messages")
def get_conversation_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某个会话的所有消息"""
    conv = conv_crud.get_conversation(db, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = msg_crud.get_conversation_messages(db, conv_id)

    # ★ 记录操作日志
    OperationLogger.log_conversation_event(
        db,
        action=Actions.CONVERSATION_VIEW,
        user_id=current_user.id,
        conv_title=conv.title,
        conv_id=conv_id,
        detail={"message_count": len(messages)},
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
