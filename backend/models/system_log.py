from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class SystemLog(Base, TimestampMixin):
    """
    系统日志模型 —— 记录全链路操作日志，支持用户行为审计

    模块分类:
      agent  — 通用 Agent 操作（用户/知识库/RAG/仪表盘/系统）
      chat   — 聊天相关操作（提问/会话管理）
      tool   — 工具调用操作（天气/数据库/HTTP）
    """
    __tablename__ = "system_logs"

    log_level: Mapped[str] = mapped_column(
        String(20), default="info",
        comment="日志级别: info / warning / error / system",
    )
    module: Mapped[str] = mapped_column(
        String(50), default="system",
        comment="来源模块: agent / chat / tool",
    )
    action: Mapped[str] = mapped_column(
        String(80), nullable=True,
        comment="操作分类: user.login / chat.ask / tool.weather / rag.search / …",
    )
    message: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="日志内容",
    )
    detail: Mapped[str] = mapped_column(
        Text, nullable=True, comment="详细信息(JSON)",
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True,
        comment="操作用户 ID",
    )
    ip_address: Mapped[str] = mapped_column(
        String(45), nullable=True, comment="客户端 IP 地址",
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=True,
        comment="资源类型: conversation / knowledge_doc / tool / …",
    )
    resource_id: Mapped[str] = mapped_column(
        String(50), nullable=True,
        comment="资源 ID",
    )
    execution_time_ms: Mapped[int] = mapped_column(
        Integer, nullable=True,
        comment="执行耗时(毫秒)",
    )

    def __repr__(self):
        return (
            f"<SystemLog(id={self.id},"
            f"action='{self.action}',"
            f"level='{self.log_level}',"
            f"user={self.user_id})>"
        )
