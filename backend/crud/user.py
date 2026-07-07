"""
用户 CRUD —— 纯数据库操作
"""
from typing import Optional
from sqlalchemy.orm import Session
from models.user import User


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """根据用户名查找用户"""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """根据邮箱查找用户"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """根据 ID 查找用户"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    username: str,
    email: str,
    hashed_password: str,
) -> User:
    """创建新用户"""
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_email(db: Session, user: User, new_email: str) -> User:
    """更新用户邮箱"""
    user.email = new_email
    db.commit()
    db.refresh(user)
    return user


def update_user_password(db: Session, user: User, new_hashed_password: str) -> User:
    """更新用户密码"""
    user.hashed_password = new_hashed_password
    db.commit()
    db.refresh(user)
    return user


def get_users_by_ids(db: Session, user_ids: set[int]) -> dict[int, str]:
    """批量查询用户名（用于日志列表展示）"""
    if not user_ids:
        return {}
    rows = db.query(User).filter(User.id.in_(user_ids)).all()
    return {u.id: u.username for u in rows}
