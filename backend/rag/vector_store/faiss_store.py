"""FAISS 向量存储（默认后端）—— 本地文件索引，无需外部服务

VECTOR_STORE_PROVIDER=faiss 时使用，所有用户共享同一个知识库索引。
内存缓存索引和文档，避免每次搜索从磁盘重新加载。
"""
import pickle
from pathlib import Path
import faiss
import numpy as np
from logs.logger import logger

VECTOR_DIM = 1024
BASE_DIR = Path(__file__).resolve().parent.parent / "data"
BASE_DIR.mkdir(parents=True, exist_ok=True)

_STORE_DIR = BASE_DIR / "vector_index_shared"
_STORE_DIR.mkdir(parents=True, exist_ok=True)

# ====== 内存缓存（启动后首次加载，写操作后清缓存） ======
_index_cache: faiss.IndexFlatIP | None = None
_docs_cache: list[dict] | None = None


def _invalidate_cache():
    """写操作后清除缓存，下次搜索时重新从磁盘加载"""
    global _index_cache, _docs_cache
    _index_cache = None
    _docs_cache = None


def _get_index() -> faiss.IndexFlatIP:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    index_file = _STORE_DIR / "index.faiss"
    if index_file.exists():
        _index_cache = faiss.read_index(str(index_file))
        logger.info(f"FAISS 索引已加载到内存: {_index_cache.ntotal} 条向量")
    else:
        _index_cache = faiss.IndexFlatIP(VECTOR_DIM)
    return _index_cache


def _save_index(index: faiss.IndexFlatIP):
    index_file = _STORE_DIR / "index.faiss"
    faiss.write_index(index, str(index_file))


def _save_docs(docs: list[dict]):
    doc_file = _STORE_DIR / "documents.pkl"
    with open(doc_file, "wb") as f:
        pickle.dump(docs, f)


def _load_docs() -> list[dict]:
    global _docs_cache
    if _docs_cache is not None:
        return _docs_cache
    doc_file = _STORE_DIR / "documents.pkl"
    if doc_file.exists():
        with open(doc_file, "rb") as f:
            _docs_cache = pickle.load(f)
        logger.info(f"FAISS 文档已加载到内存: {len(_docs_cache)} 条")
    else:
        _docs_cache = []
    return _docs_cache


def add_vectors(vectors: list[list[float]], documents: list[dict]):
    if not documents:
        return
    index = _get_index()
    arr = np.array(vectors, dtype=np.float32)
    faiss.normalize_L2(arr)
    index.add(arr)
    _save_index(index)
    docs = _load_docs()
    docs.extend(documents)
    _save_docs(docs)
    # 写操作后清除缓存，下次读取时重新加载最新数据
    _invalidate_cache()


def search(query_vec: list[float], top_k: int = 5, user_id: int | None = None) -> list[dict]:
    index = _get_index()
    if index.ntotal == 0:
        return []
    arr = np.array([query_vec], dtype=np.float32)
    faiss.normalize_L2(arr)
    search_width = min(index.ntotal, max(top_k * 5, 20))
    scores, indices = index.search(arr, search_width)
    docs = _load_docs()
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        doc = docs[idx]
        doc_user_id = (doc.get("metadata") or {}).get("user_id")
        if user_id is not None and doc_user_id != user_id:
            continue
        if user_id is not None and score <= 0:
            continue
        if len(results) >= top_k:
            break
        results.append({"score": round(float(score), 4), **doc})
    return results


def count() -> int:
    return _get_index().ntotal


def remove_by_source(source: str) -> int:
    index = _get_index()
    ntotal = index.ntotal
    if ntotal == 0:
        return 0
    docs = _load_docs()
    if not docs:
        return 0
    all_vectors = np.zeros((ntotal, VECTOR_DIM), dtype=np.float32)
    for i in range(ntotal):
        all_vectors[i] = index.reconstruct(i)
    keep_mask = np.ones(ntotal, dtype=bool)
    for i, doc in enumerate(docs):
        if doc.get("source") == source:
            keep_mask[i] = False
    removed = int((~keep_mask).sum())
    if removed == 0:
        return 0
    new_index = faiss.IndexFlatIP(VECTOR_DIM)
    kept_vectors = all_vectors[keep_mask]
    if len(kept_vectors) > 0:
        faiss.normalize_L2(kept_vectors)
        new_index.add(kept_vectors)
    _save_index(new_index)
    kept_docs = [doc for i, doc in enumerate(docs) if keep_mask[i]]
    _save_docs(kept_docs)
    # 写操作后清除缓存
    _invalidate_cache()
    return removed


def backfill_legacy_metadata() -> int:
    """Assign owners to FAISS records created before metadata isolation.

    Legacy records used the KnowledgeDoc title as source. Unmatched records stay
    hidden because returning them to every user would violate isolation.
    """
    docs = _load_docs()
    if not docs or not any((doc.get("metadata") or {}).get("user_id") is None for doc in docs):
        return 0
    from database.session import SessionLocal
    from models.knowledge_doc import KnowledgeDoc

    db = SessionLocal()
    changed = 0
    try:
        records = db.query(KnowledgeDoc).all()
        by_title: dict[str, KnowledgeDoc] = {}
        by_source: dict[str, KnowledgeDoc] = {}
        for record in records:
            by_title.setdefault(record.title, record)
            if record.source:
                by_source.setdefault(Path(record.source).name, record)
        for doc in docs:
            metadata = doc.setdefault("metadata", {})
            if metadata.get("user_id") is not None:
                continue
            owner = by_title.get(doc.get("source", "")) or by_source.get(doc.get("source", ""))
            if owner:
                metadata["user_id"] = owner.user_id
                metadata.setdefault("file_id", owner.id)
                changed += 1
        if changed:
            _save_docs(docs)
            _invalidate_cache()
        return changed
    finally:
        db.close()

def remove_by_file_id(file_id: int, source: str | None = None) -> int:
    """Remove chunks for one KnowledgeDoc; source is the legacy-data fallback."""
    index = _get_index()
    ntotal = index.ntotal
    if ntotal == 0:
        return 0
    docs = _load_docs()
    if not docs:
        return 0
    all_vectors = np.zeros((ntotal, VECTOR_DIM), dtype=np.float32)
    for i in range(ntotal):
        all_vectors[i] = index.reconstruct(i)
    keep_mask = np.ones(ntotal, dtype=bool)
    for i, doc in enumerate(docs):
        metadata = doc.get("metadata") or {}
        if metadata.get("file_id") == file_id:
            keep_mask[i] = False
        elif metadata.get("user_id") is None and source and doc.get("source") == source:
            keep_mask[i] = False
    removed = int((~keep_mask).sum())
    if removed == 0:
        return 0
    new_index = faiss.IndexFlatIP(VECTOR_DIM)
    kept_vectors = all_vectors[keep_mask]
    if len(kept_vectors) > 0:
        faiss.normalize_L2(kept_vectors)
        new_index.add(kept_vectors)
    _save_index(new_index)
    _save_docs([doc for i, doc in enumerate(docs) if keep_mask[i]])
    _invalidate_cache()
    return removed


def clear():
    import shutil as _su
    _su.rmtree(_STORE_DIR, ignore_errors=True)
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    _invalidate_cache()
