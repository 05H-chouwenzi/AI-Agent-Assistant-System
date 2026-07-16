"""知识库向量模型 —— pgvector 向量存储表（可选，替换 FAISS）

使用方式：
  1. 在 docker-compose 中启用 PostgreSQL + pgvector
  2. 设置 VECTOR_STORE_PROVIDER=pgvector
  3. 设置 PGVECTOR_DATABASE_URL 连接 PostgreSQL
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text, Float, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin

VECTOR_DIM = 1024  # 匹配 text-embedding-v3 的向量维度


class KnowledgeVector(Base, TimestampMixin):
    """知识库向量块 — 每个 chunk 一条记录，含向量"""
    __tablename__ = "knowledge_vectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="关联的 KnowledgeDoc ID",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer, default=0, comment="文档内的块序号",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="文本块内容",
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(VECTOR_DIM), nullable=False, comment="向量嵌入",
    )
    source: Mapped[str] = mapped_column(
        String(500), nullable=True, comment="来源文件名/URL",
    )
    score: Mapped[float] = mapped_column(
        Float, nullable=True, comment="检索时的相关度得分（不持久化）",
    )

    __table_args__ = (
        Index("idx_kv_source", "source"),
        Index("idx_kv_doc_id", "doc_id"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "source": self.source,
            "score": self.score,
        }

    def __repr__(self):
        return f"<KnowledgeVector(id={self.id}, doc_id={self.doc_id}, chunk={self.chunk_index})>"
