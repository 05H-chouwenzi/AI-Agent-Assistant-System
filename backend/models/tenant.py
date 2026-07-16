"""Tenant 模型 —— 多租户支持（轻量版）"""
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class Tenant(Base, TimestampMixin):
    """租户表"""
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="租户名称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否激活"
    )

    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}')>"


# 预定义角色
TENANT_ROLES = ("admin", "member")
