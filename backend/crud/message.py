"""
消息 CRUD —— 纯数据库操作
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.message import Message


def get_conversation_messages(db: Session, conv_id: int) -> list[Message]:
    """获取会话的所有消息（按时间正序）"""
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )


def get_last_message(db: Session, conv_id: int) -> Optional[Message]:
    """获取会话的最后一条消息"""
    return (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .first()
    )


def create_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    token_count: int = 0,
) -> Message:
    """创建消息"""
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        token_count=token_count,
    )
    db.add(msg)
    return msg


def count_today_messages(db: Session, user_id: int, today_start) -> int:
    """统计用户今日消息数"""
    from models.conversation import Conversation

    return (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(
            Conversation.user_id == user_id,
            Message.created_at >= today_start,
        )
        .scalar()
        or 0
    )


def count_user_messages(db: Session, user_id: int) -> int:
    """统计用户总消息数"""
    from models.conversation import Conversation

    return (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
        .scalar()
        or 0
    )


def count_user_messages_by_role(db: Session, user_id: int, role: str) -> int:
    """按角色统计用户消息数"""
    from models.conversation import Conversation

    return (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, Message.role == role)
        .scalar()
        or 0
    )


def sum_user_tokens(db: Session, user_id: int, since=None) -> int:
    """统计用户 Token 消耗，可指定起始时间"""
    from models.conversation import Conversation

    q = (
        db.query(func.coalesce(func.sum(Message.token_count), 0))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
    )
    if since is not None:
        q = q.filter(Message.created_at >= since)
    return q.scalar() or 0
