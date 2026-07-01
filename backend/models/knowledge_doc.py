"""
知识库文档模型 —— RAG 知识库的文档
"""
from sqlalchemy import Column,String,Text,Integer,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column,relationship

from .base import Base,TimestampMixin

class KnowledgeDoc(Base,TimestampMixin):
    """
    知识文档表
    """
    __tablename__="knowledge_docs"

    user_id:Mapped[int]=mapped_column(
        Integer,ForeignKey("users.id"),nullable=False,comment="上传用户ID"
    )
    title:Mapped[str]=mapped_column(
        String(300),nullable=False,comment="文档标题"
    )
    content:Mapped[str]=mapped_column(
        Text,nullable=False,comment="文档原始内容"
    )
    file_type:Mapped[str]=mapped_column(
        String(20),default="txt",comment="文件类型:txt/pdf/md/docx/xlsx/pptx/png"
    )
    source:Mapped[str]=mapped_column(
        String(500),nullable=True,comment="来源路径或URL"
    )
    status:Mapped[str]=mapped_column(
        String(20),default="pending",
        comment="状态:pending/processing/completed/failed"
    )

    owner = relationship("User", backref="knowledge_docs")

    def __repr__(self):
        return f"<KnowledgeDoc(id={self.id},title='{self.title}')>"
