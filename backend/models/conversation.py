"""
对话模型 —— 一次完整的用户对话会话
"""

from sqlalchemy import Column,String,Text
from sqlalchemy.orm import Mapped,mapped_column,relationship

from .base import Base,TimestampMixin

class Conversation(Base,TimestampMixin):

    # 对话表
    
    # 字段说明：
    # - id         : 主键
    # - title      : 对话标题
    # - user_id    : 所属用户 ID（外键，先不加约束，后面统一处理）
    # - status     : 状态（active / archived）
    # - messages   : 关联的消息列表（ORM 关系）
    
    __tablename__="conversations"
    title:Mapped[str]=mapped_column(
        String(200),default="新对话",comment="对话标题"
    )
    user_id: Mapped[int]=mapped_column(comment="所属用户ID")
    status:Mapped[str]=mapped_column(
        String(20),default="active",comment="状态:active/archived"
    )

    # 关联 Message —— 仅在需要时显式加载
    messages = relationship("Message", back_populates="conversation")

    def __repr__(self):
        return f"<Conversation(id={self.id},title='{self.title}')>"