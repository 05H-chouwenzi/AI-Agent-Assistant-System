"""
Dashboard 统计路由 —— 提供首页仪表盘的真实数据
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from pydantic import BaseModel

from database.session import get_db
from models.message import Message
from models.conversation import Conversation
from models.knowledge_doc import KnowledgeDoc
from models.user import User
from models.system_log import SystemLog
from utils.auth import get_current_user
from tools.tool_manager import get_tool_manager
from config.settings import LLM_MODEL

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘统计数据"""
    try:
        # 模型用的是 datetime.utcnow（naive），这里保持一致
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. 今日消息数
        today_call_count = (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.user_id == current_user.id,
                Message.created_at >= today_start,
            )
            .scalar()
            or 0
        )

        # 2. 知识库文档数（全部用户）
        doc_count = (
            db.query(func.count(KnowledgeDoc.id))
            .scalar()
            or 0
        )

        # 3. 工具数
        try:
            manager = get_tool_manager()
            tool_count = len(manager.list_tools())
        except Exception:
            tool_count = 0

        # 4. 总对话数
        total_conversations = (
            db.query(func.count(Conversation.id))
            .filter(Conversation.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 5. 总消息数
        total_messages = (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == current_user.id)
            .scalar()
            or 0
        )

        # 6. User/Assistant 消息比例
        user_msg_count = (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == current_user.id, Message.role == "user")
            .scalar()
            or 0
        )
        assistant_msg_count = (
            db.query(func.count(Message.id))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == current_user.id, Message.role == "assistant")
            .scalar()
            or 0
        )

        # 7. Token 消耗
        total_tokens = (
            db.query(func.coalesce(func.sum(Message.token_count), 0))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(Conversation.user_id == current_user.id)
            .scalar()
            or 0
        )
        today_tokens = (
            db.query(func.coalesce(func.sum(Message.token_count), 0))
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.user_id == current_user.id,
                Message.created_at >= today_start,
            )
            .scalar()
            or 0
        )

        # 8. 账号天数
        if current_user.created_at:
            account_age_days = (datetime.utcnow() - current_user.created_at).days
        else:
            account_age_days = 0

        # 9. 最近聊天（最近5条活跃会话 + 最后一条消息预览）
        conversations = (
            db.query(Conversation)
            .filter(Conversation.user_id == current_user.id, Conversation.status == "active")
            .order_by(Conversation.updated_at.desc())
            .limit(5)
            .all()
        )

        recent_conversations = []
        for conv in conversations:
            last_msg = (
                db.query(Message)
                .filter(Message.conversation_id == conv.id)
                .order_by(Message.created_at.desc())
                .first()
            )
            recent_conversations.append({
                "id": conv.id,
                "title": conv.title,
                "last_message": last_msg.content[:120] if last_msg else "",
                "last_time": last_msg.created_at.strftime("%Y-%m-%d %H:%M")
                if last_msg and last_msg.created_at else "",
            })

        return {
            "today_call_count": today_call_count,
            "doc_count": doc_count,
            "tool_count": tool_count,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "user_msg_count": user_msg_count,
            "assistant_msg_count": assistant_msg_count,
            "total_tokens": total_tokens,
            "today_tokens": today_tokens,
            "account_age_days": account_age_days,
            "recent_conversations": recent_conversations,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
def get_dashboard_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取近 7 天每日趋势数据"""
    try:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today - timedelta(days=6)

        # 每日消息数（按日期分组）
        daily_message_rows = (
            db.query(
                cast(Message.created_at, Date).label("msg_date"),
                func.count(Message.id).label("cnt"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.user_id == current_user.id,
                Message.created_at >= seven_days_ago,
            )
            .group_by(cast(Message.created_at, Date))
            .order_by(cast(Message.created_at, Date))
            .all()
        )

        # 每日新对话数
        daily_conv_rows = (
            db.query(
                cast(Conversation.created_at, Date).label("conv_date"),
                func.count(Conversation.id).label("cnt"),
            )
            .filter(
                Conversation.user_id == current_user.id,
                Conversation.created_at >= seven_days_ago,
            )
            .group_by(cast(Conversation.created_at, Date))
            .order_by(cast(Conversation.created_at, Date))
            .all()
        )

        # 每日 Token 消耗
        daily_token_rows = (
            db.query(
                cast(Message.created_at, Date).label("msg_date"),
                func.coalesce(func.sum(Message.token_count), 0).label("tokens"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.user_id == current_user.id,
                Message.created_at >= seven_days_ago,
            )
            .group_by(cast(Message.created_at, Date))
            .order_by(cast(Message.created_at, Date))
            .all()
        )

        # 构建日期→值的映射
        msg_map = {str(r.msg_date): r.cnt for r in daily_message_rows}
        conv_map = {str(r.conv_date): r.cnt for r in daily_conv_rows}
        token_map = {str(r.msg_date): r.tokens for r in daily_token_rows}

        # 填充 7 天（包括无数据的日期补零）
        daily_messages = []
        daily_conversations = []
        daily_tokens = []
        for i in range(7):
            day = (seven_days_ago + timedelta(days=i))
            day_str = day.strftime("%m-%d")
            date_key = day.strftime("%Y-%m-%d")
            daily_messages.append({"date": day_str, "count": msg_map.get(date_key, 0)})
            daily_conversations.append({"date": day_str, "count": conv_map.get(date_key, 0)})
            daily_tokens.append({"date": day_str, "tokens": token_map.get(date_key, 0)})

        return {
            "daily_messages": daily_messages,
            "daily_conversations": daily_conversations,
            "daily_tokens": daily_tokens,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
def get_system_status(db: Session = Depends(get_db)):
    """获取系统级状态信息"""
    try:
        # 1. 数据库连接检测
        db_status = "connected"
        try:
            db.execute(func.now())
        except Exception:
            db_status = "disconnected"

        # 2. 版本号（从 APP_VERSION 或固定值读取）
        version = "0.1.0"

        # 3. 最近日志摘要
        recent_logs = (
            db.query(SystemLog)
            .order_by(SystemLog.created_at.desc())
            .limit(5)
            .all()
        )
        last_log_summary = [
            {
                "id": log.id,
                "level": log.log_level,
                "module": log.module,
                "message": log.message[:100],
                "time": log.created_at.strftime("%m-%d %H:%M")
                if log.created_at else "",
            }
            for log in recent_logs
        ]

        return {
            "db_status": db_status,
            "version": version,
            "server_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "model": LLM_MODEL,
            "last_log_summary": last_log_summary,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
