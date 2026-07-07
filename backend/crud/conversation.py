"""
会话 CRUD —— 纯数据库操作
"""
from typing import Optional
from sqlalchemy.orm import Session
from models.conversation import Conversation


def create_conversation(db: Session, title: str, user_id: int) -> Conversation:
    """创建新会话"""
    conv = Conversation(title=title, user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_user_active_conversations(db: Session, user_id: int) -> list[Conversation]:
    """获取用户活跃会话列表（按更新时间倒序）"""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def get_conversation(db: Session, conv_id: int, user_id: int) -> Optional[Conversation]:
    """获取用户的某个会话（带用户权限检查）"""
    return (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == user_id)
        .first()
    )


def archive_conversation(db: Session, conv_id: int, user_id: int) -> Optional[Conversation]:
    """软删除会话（设为 archived 状态）"""
    conv = get_conversation(db, conv_id, user_id)
    if not conv:
        return None
    conv.status = "archived"
    db.commit()
    return conv


def get_recent_conversations(
    db: Session, user_id: int, limit: int = 5
) -> list[Conversation]:
    """获取最近的 N 条活跃会话"""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def count_user_conversations(db: Session, user_id: int) -> int:
    """统计用户总对话数"""
    return (
        db.query(Conversation.id)
        .filter(Conversation.user_id == user_id)
        .count()
    )
