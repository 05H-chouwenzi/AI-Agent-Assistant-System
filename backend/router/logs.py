"""
日志路由 —— 查询 system_logs 表（支持按分类/用户过滤）
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from crud import system_log as log_crud
from crud import user as user_crud

router = APIRouter(prefix="/api/logs", tags=["日志"])


@router.get("/")
def list_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    module: str = Query(None),
    level: str = Query(None),
    action: str = Query(None, description="操作分类，如 user.login / chat.ask / tool.weather"),
    user_id: int = Query(None, description="按用户 ID 过滤"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """查询系统日志，按时间倒序，支持按分类/模块/级别/用户过滤"""
    total, items = log_crud.list_logs(db, page, page_size, module, level, action, user_id)

    # 批量查询用户名
    user_ids = {log.user_id for log in items if log.user_id}
    users = user_crud.get_users_by_ids(db, user_ids)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "level": log.log_level,
                "module": log.module,
                "action": log.action,
                "message": log.message,
                "detail": log.detail,
                "user_id": log.user_id,
                "username": users.get(log.user_id) if log.user_id else None,
                "ip_address": log.ip_address,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "execution_time_ms": log.execution_time_ms,
                "time": str(log.created_at) if log.created_at else None,
            }
            for log in items
        ],
    }


@router.get("/actions")
def list_actions(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取所有已使用的操作分类列表（去重）"""
    return {"actions": log_crud.list_distinct_actions(db)}


@router.get("/modules")
def list_modules(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取所有已使用的模块列表（去重）"""
    return {"modules": log_crud.list_distinct_modules(db)}
