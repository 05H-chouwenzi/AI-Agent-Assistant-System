"""
日志路由 —— 查询 system_logs 表
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.session import get_db
from models.system_log import SystemLog
from models.user import User
from utils.auth import get_current_user

router = APIRouter(prefix="/api/logs", tags=["日志"])


@router.get("/")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: str = Query(None),
    level: str = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """查询系统日志，按时间倒序"""
    q = db.query(SystemLog)

    if module:
        q = q.filter(SystemLog.module == module)
    if level:
        q = q.filter(SystemLog.log_level == level)

    total = q.count()
    items = (
        q.order_by(desc(SystemLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "level": log.log_level,
                "module": log.module,
                "message": log.message,
                "detail": log.detail,
                "time": str(log.created_at) if log.created_at else None,
            }
            for log in items
        ],
    }
