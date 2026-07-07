"""
仪表盘统计 CRUD —— 纯数据库操作（聚合查询）
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, case
from models.conversation import Conversation
from models.message import Message
from models.knowledge_doc import KnowledgeDoc


def get_today_message_count(db: Session, user_id: int) -> int:
    """获取用户今日消息数"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, Message.created_at >= today_start)
        .scalar()
        or 0
    )


def get_total_doc_count(db: Session) -> int:
    """获取知识库文档总数"""
    return db.query(func.count(KnowledgeDoc.id)).scalar() or 0


def get_message_stats(db: Session, user_id: int) -> dict:
    """获取用户消息统计 —— 合并为单次查询"""
    rows = (
        db.query(
            func.count(Message.id).label("total"),
            func.sum(case((Message.role == "user", 1), else_=0)).label("user_count"),
            func.sum(case((Message.role == "assistant", 1), else_=0)).label("assistant_count"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
        .first()
    )

    return {
        "total": rows.total or 0,
        "user_count": rows.user_count or 0,
        "assistant_count": rows.assistant_count or 0,
    }


def get_token_stats(db: Session, user_id: int) -> dict:
    """获取用户 Token 消耗统计 —— 合并为单次查询"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    row = (
        db.query(
            func.coalesce(func.sum(Message.token_count), 0).label("total"),
            func.coalesce(
                func.sum(
                    case((Message.created_at >= today_start, Message.token_count), else_=0)
                ),
                0,
            ).label("today"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id)
        .first()
    )

    return {"total": row.total or 0, "today": row.today or 0}


def get_recent_conversations_with_last_message(
    db: Session, user_id: int, limit: int = 5
) -> list[dict]:
    """获取最近 N 条活跃会话及最后消息 —— 一次查询解决 N+1"""

    # 子查询：每个会话的最后一条消息
    last_msg_sub = (
        db.query(
            Message.conversation_id,
            Message.content.label("last_content"),
            Message.created_at.label("last_time"),
        )
        .distinct(Message.conversation_id)
        .order_by(Message.conversation_id, Message.created_at.desc())
        .subquery()
    )

    rows = (
        db.query(
            Conversation.id,
            Conversation.title,
            last_msg_sub.c.last_content,
            last_msg_sub.c.last_time,
        )
        .outerjoin(last_msg_sub, Conversation.id == last_msg_sub.c.conversation_id)
        .filter(
            Conversation.user_id == user_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "title": row.title,
            "last_message": (row.last_content[:120] if row.last_content else ""),
            "last_time": (
                row.last_time.strftime("%Y-%m-%d %H:%M")
                if row.last_time else ""
            ),
        }
        for row in rows
    ]


def get_daily_message_trends(
    db: Session, user_id: int, days: int = 7
) -> list[dict]:
    """获取每日消息趋势"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)

    rows = (
        db.query(
            cast(Message.created_at, Date).label("msg_date"),
            func.count(Message.id).label("cnt"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, Message.created_at >= since)
        .group_by(cast(Message.created_at, Date))
        .order_by(cast(Message.created_at, Date))
        .all()
    )
    return _fill_daily(since, days, rows, "cnt", "count")


def get_daily_conversation_trends(
    db: Session, user_id: int, days: int = 7
) -> list[dict]:
    """获取每日新对话趋势"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)

    rows = (
        db.query(
            cast(Conversation.created_at, Date).label("conv_date"),
            func.count(Conversation.id).label("cnt"),
        )
        .filter(Conversation.user_id == user_id, Conversation.created_at >= since)
        .group_by(cast(Conversation.created_at, Date))
        .order_by(cast(Conversation.created_at, Date))
        .all()
    )
    return _fill_daily(since, days, rows, "cnt", "count")


def get_daily_token_trends(
    db: Session, user_id: int, days: int = 7
) -> list[dict]:
    """获取每日 Token 消耗趋势"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    since = today - timedelta(days=days - 1)

    rows = (
        db.query(
            cast(Message.created_at, Date).label("msg_date"),
            func.coalesce(func.sum(Message.token_count), 0).label("tokens"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, Message.created_at >= since)
        .group_by(cast(Message.created_at, Date))
        .order_by(cast(Message.created_at, Date))
        .all()
    )
    return _fill_daily(since, days, rows, "tokens", "tokens")


def _fill_daily(since, days: int, rows, val_key: str, out_key: str) -> list[dict]:
    """填充 N 天数据，缺失日期补零"""
    val_map = {str(r[0]): r[1] for r in rows}
    result = []
    for i in range(days):
        day = since + timedelta(days=i)
        result.append({
            "date": day.strftime("%m-%d"),
            out_key: val_map.get(day.strftime("%Y-%m-%d"), 0),
        })
    return result


def check_db_connection(db: Session) -> bool:
    """检测数据库连接是否正常"""
    try:
        db.execute(func.now())
        return True
    except Exception:
        return False
