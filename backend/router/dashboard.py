"""
Dashboard 统计路由 —— 提供首页仪表盘的真实数据
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from tools.tool_manager import get_tool_manager
from config.settings import LLM_MODEL
from crud import dashboard as dash_crud
from crud import conversation as conv_crud
from crud import system_log as log_crud

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


@router.get("/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取仪表盘统计数据"""
    try:
        today_call_count = dash_crud.get_today_message_count(db, current_user.id)
        doc_count = dash_crud.get_total_doc_count(db)

        try:
            manager = get_tool_manager()
            tool_count = len(manager.list_tools())
        except Exception:
            tool_count = 0

        total_conversations = conv_crud.count_user_conversations(db, current_user.id)

        msg_stats = dash_crud.get_message_stats(db, current_user.id)

        token_stats = dash_crud.get_token_stats(db, current_user.id)

        # 账号天数
        if current_user.created_at:
            account_age_days = (datetime.utcnow() - current_user.created_at).days
        else:
            account_age_days = 0

        # 最近聊天（最近5条活跃会话 + 最后一条消息，一次查询）
        recent_conversations = dash_crud.get_recent_conversations_with_last_message(
            db, current_user.id, limit=5
        )

        return {
            "today_call_count": today_call_count,
            "doc_count": doc_count,
            "tool_count": tool_count,
            "total_conversations": total_conversations,
            "total_messages": msg_stats["total"],
            "user_msg_count": msg_stats["user_count"],
            "assistant_msg_count": msg_stats["assistant_count"],
            "total_tokens": token_stats["total"],
            "today_tokens": token_stats["today"],
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
        return {
            "daily_messages": dash_crud.get_daily_message_trends(db, current_user.id, days=7),
            "daily_conversations": dash_crud.get_daily_conversation_trends(db, current_user.id, days=7),
            "daily_tokens": dash_crud.get_daily_token_trends(db, current_user.id, days=7),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
def get_system_status(db: Session = Depends(get_db)):
    """获取系统级状态信息"""
    try:
        db_status = "connected" if dash_crud.check_db_connection(db) else "disconnected"
        version = "0.1.0"

        recent_logs = log_crud.get_recent_logs(db, limit=5)
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
