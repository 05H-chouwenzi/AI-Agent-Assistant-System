from sqlalchemy import Column,String,Text
from sqlalchemy.orm import Mapped,mapped_column

from .base import Base,TimestampMixin

class SystemLog(Base,TimestampMixin):
    """
    系统日志模型
    """
    __tablename__="system_logs"
    log_level:Mapped[str]=mapped_column(
        String(20),default="system",comment="日志级别:info/warning/error/system"
    )
    module:Mapped[str]=mapped_column(
        String(50),default="system",comment="来源模块:agent/rag/tool/api"
    )
    message:Mapped[str]=mapped_column(
        String(500),nullable=False,comment="日志内容"
    )
    detail:Mapped[str]=mapped_column(
        Text,nullable=True,comment="详细信息(JSON)"
    )
    def __repr__(self):
        return f"<SystemLog(id={self.id},level='{self.log_level}',module='{self.module}')>"