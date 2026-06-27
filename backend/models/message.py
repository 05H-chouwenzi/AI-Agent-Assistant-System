"""
消息模型 —— 对话中的每一条聊天记录
"""
from sqlalchemy import Column,Integer,String,Text,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column,relationship

from .base import Base,TimestampMixin

class Message(Base,TimestampMixin):
    """
    消息表
    
    字段说明：
    - id              : 主键
    - conversation_id : 所属对话 ID
    - role            : 角色（user / assistant / system）
    - content         : 消息内容
    - token_count     : Token 消耗数（可选）
    """
    __tablename__="messages"
    conversation_id:Mapped[int]=mapped_column(
        Integer,ForeignKey("conversations.id"),comment="所属对话ID"
    )
    role:Mapped[str]=mapped_column(
        String(20),nullable=False,comment="角色:user/assistant/system"
    )
    content:Mapped[str]=mapped_column(
        Text,nullable=False,comment="消息内容"
    )
    token_count:Mapped[int]=mapped_column(
        Integer,default=0,comment="消耗数"
    )

    conversation=relationship("Conversation",back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id},role='{self.role}')>"