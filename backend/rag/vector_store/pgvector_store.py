"""pgvector 向量存储 —— 替代 FAISS，使用 PostgreSQL + pgvector

依赖:
  pip install pgvector psycopg2-binary sqlalchemy

在 .env 中设置以下内容启用 pgvector:
  VECTOR_STORE_PROVIDER=pgvector
  PGVECTOR_DATABASE_URL=postgresql+psycopg2://user:pass@pgvector-db:5432/ai_assistant

注意：pgvector 需在 PostgreSQL 中启用 CREATE EXTENSION vector;
"""
import logging
import time
from typing import Optional

import numpy as np
from sqlalchemy import create_event_listener, text as sa_text
from sqlalchemy.orm import Session as SASession, sessionmaker

from config.settings import (
    VECTOR_STORE_PROVIDER,
    PGVECTOR_DATABASE_URL,
)
from models.knowledge_vector import KnowledgeVector, VECTOR_DIM

logger = logging.getLogger("agent")

# ====== 全局连接（惰性初始化） ======
_engine = None
_SessionLocal: Optional[sessionmaker] = None


def _get_session() -> SASession:
    """获取 pgvector 数据库会话（首次调用时自动创建连接）"""
    global _engine, _SessionLocal

    if _SessionLocal is not None:
        return _SessionLocal()

    if not PGVECTOR_DATABASE_URL:
        raise RuntimeError(
            "pgvector 已启用 (VECTOR_STORE_PROVIDER=pgvector) "
            "但未设置 PGVECTOR_DATABASE_URL"
        )

    from sqlalchemy import create_engine

    _engine = create_engine(PGVECTOR_DATABASE_URL, pool_pre_ping=True)

    # 启用 pgvector 扩展并建表
    with _engine.connect() as conn:
        conn.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    KnowledgeVector.metadata.create_all(bind=_engine)

    _SessionLocal = sessionmaker(bind=_engine)
    logger.info("pgvector 连接已建立，表已就绪")
    return _SessionLocal()


# ====== 公开 API（与 FAISS 版 vector_store 接口一致）======

def add_vectors(vectors: list[list[float]], documents: list[dict]):
    """批量添加向量及文档到 pgvector"""
    if not documents or not vectors:
        return
    assert len(vectors) == len(documents), "vectors 和 documents 长度必须一致"

    session = _get_session()
    try:
        rows = []
        for vec, doc in zip(vectors, documents):
            rows.append(KnowledgeVector(
                doc_id=doc.get("id", 0),
                chunk_index=doc.get("chunk_index", 0),
                content=doc.get("content", ""),
                embedding=vec,
                source=doc.get("source"),
            ))
        session.add_all(rows)
        session.commit()
        logger.info(f"pgvector: 添加 {len(rows)} 条向量")
    except Exception as e:
        session.rollback()
        logger.error(f"pgvector 添加失败: {e}")
        raise
    finally:
        session.close()


def search(query_vec: list[float], top_k: int = 5) -> list[dict]:
    """用余弦相似度检索 top_k 个文档"""
    session = _get_session()
    try:
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = sa_text(
            f"SELECT id, doc_id, chunk_index, content, source, "
            f"1 - (embedding <=> :query_vec) AS score "
            f"FROM knowledge_vectors "
            f"ORDER BY embedding <=> :query_vec2 "
            f"LIMIT :top_k"
        )
        rows = session.execute(
            sql,
            {"query_vec": vec_str, "query_vec2": vec_str, "top_k": top_k},
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "doc_id": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "source": row[4],
                "score": round(float(row[5]), 4),
            })
        return results
    except Exception as e:
        logger.error(f"pgvector 检索失败: {e}")
        return []
    finally:
        session.close()


def count() -> int:
    """向量总数"""
    session = _get_session()
    try:
        return session.query(KnowledgeVector).count()
    finally:
        session.close()


def remove_by_source(source: str) -> int:
    """按 source 删除所有向量块"""
    session = _get_session()
    try:
        deleted = (
            session.query(KnowledgeVector)
            .filter(KnowledgeVector.source == source)
            .delete()
        )
        session.commit()
        return deleted
    except Exception as e:
        session.rollback()
        logger.error(f"pgvector 删除失败: {e}")
        return 0
    finally:
        session.close()


def clear():
    """清空所有向量"""
    session = _get_session()
    try:
        session.query(KnowledgeVector).delete()
        session.commit()
        logger.info("pgvector: 已清空所有向量")
    except Exception as e:
        session.rollback()
        logger.error(f"pgvector 清空失败: {e}")
    finally:
        session.close()


def is_available() -> bool:
    """检查 pgvector 是否可用（连接正常 + 扩展已启用）"""
    try:
        session = _get_session()
        session.execute(sa_text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        try:
            session.close()
        except Exception:
            pass
