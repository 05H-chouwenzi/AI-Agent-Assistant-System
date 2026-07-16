"""向量存储 —— 支持 FAISS（默认）和 pgvector（可选）两种后端

    在 .env 中设置 VECTOR_STORE_PROVIDER 切换：
      VECTOR_STORE_PROVIDER=faiss      （默认，使用本地 FAISS 索引文件）
      VECTOR_STORE_PROVIDER=pgvector   （替换，使用 PostgreSQL + pgvector）

    pgvector 模式需额外配置 PGVECTOR_DATABASE_URL。
"""
import logging
from typing import Callable

from config.settings import VECTOR_STORE_PROVIDER

logger = logging.getLogger("agent")

# 默认导出 FAISS 实现
from rag.vector_store.faiss_store import (  # type: ignore
    add_vectors as _faiss_add_vectors,
    search as _faiss_search,
    count as _faiss_count,
    remove_by_source as _faiss_remove_by_source,
    clear as _faiss_clear,
)

# ====== 根据配置选择后端 ======

def _resolve_implementation():
    """根据 VECTOR_STORE_PROVIDER 选择后端实现"""
    if VECTOR_STORE_PROVIDER == "pgvector":
        try:
            from rag.vector_store.pgvector_store import (
                add_vectors as _pg_add,
                search as _pg_search,
                count as _pg_count,
                remove_by_source as _pg_remove,
                clear as _pg_clear,
                is_available,
            )
            if is_available():
                logger.info("向量存储: 使用 pgvector 后端")
                return _pg_add, _pg_search, _pg_count, _pg_remove, _pg_clear
            else:
                logger.warning("pgvector 不可用，回退到 FAISS")
        except Exception as e:
            logger.warning(f"pgvector 加载失败 ({e})，回退到 FAISS")
    else:
        logger.debug(f"向量存储: 使用 FAISS 后端 (VECTOR_STORE_PROVIDER={VECTOR_STORE_PROVIDER})")

    return (_faiss_add_vectors, _faiss_search,
            _faiss_count, _faiss_remove_by_source, _faiss_clear)


_add_vectors, _search, _count, _remove_by_source, _clear = _resolve_implementation()


# ====== 统一导出，接口与 FAISS 版完全一致 ======

def add_vectors(vectors: list[list[float]], documents: list[dict]):
    return _add_vectors(vectors, documents)


def search(query_vec: list[float], top_k: int = 5) -> list[dict]:
    return _search(query_vec, top_k=top_k)


def count() -> int:
    return _count()


def remove_by_source(source: str) -> int:
    return _remove_by_source(source)


def clear():
    return _clear()
