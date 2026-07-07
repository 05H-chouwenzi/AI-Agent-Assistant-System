"""
系统日志 CRUD —— 纯数据库操作
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models.system_log import SystemLog


def list_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    module: Optional[str] = None,
    level: Optional[str] = None,
    action: Optional[str] = None,
    user_id: Optional[int] = None,
) -> tuple[int, list[SystemLog]]:
    """分页查询系统日志，返回 (总数, 当前页列表)"""
    q = db.query(SystemLog)

    if module:
        q = q.filter(SystemLog.module == module)
    if level:
        q = q.filter(SystemLog.log_level == level)
    if action:
        q = q.filter(SystemLog.action == action)
    if user_id:
        q = q.filter(SystemLog.user_id == user_id)

    total = q.count()
    items = (
        q.order_by(desc(SystemLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return total, items


def list_distinct_actions(db: Session) -> list[str]:
    """获取所有已使用的操作分类（去重）"""
    results = (
        db.query(SystemLog.action)
        .filter(SystemLog.action.isnot(None))
        .distinct()
        .order_by(SystemLog.action)
        .all()
    )
    return [r[0] for r in results if r[0]]


def list_distinct_modules(db: Session) -> list[str]:
    """获取所有已使用的模块（去重）"""
    results = (
        db.query(SystemLog.module)
        .filter(SystemLog.module.isnot(None))
        .distinct()
        .order_by(SystemLog.module)
        .all()
    )
    return [r[0] for r in results if r[0]]


def get_recent_logs(db: Session, limit: int = 5) -> list[SystemLog]:
    """获取最近 N 条日志"""
    return (
        db.query(SystemLog)
        .order_by(SystemLog.created_at.desc())
        .limit(limit)
        .all()
    )
