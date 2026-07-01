"""
向量存储 —— 全局共享 FAISS 索引（所有用户共用知识库）
"""
import pickle
from pathlib import Path
import faiss
import numpy as np

VECTOR_DIM = 1024
BASE_DIR = Path(__file__).resolve().parent.parent / "data"
BASE_DIR.mkdir(parents=True, exist_ok=True)

_STORE_DIR = BASE_DIR / "vector_index_shared"
_STORE_DIR.mkdir(parents=True, exist_ok=True)


def _get_index() -> faiss.IndexFlatIP:
    index_file = _STORE_DIR / "index.faiss"
    if index_file.exists():
        return faiss.read_index(str(index_file))
    return faiss.IndexFlatIP(VECTOR_DIM)


def _save_index(index: faiss.IndexFlatIP):
    index_file = _STORE_DIR / "index.faiss"
    faiss.write_index(index, str(index_file))


def _save_docs(docs: list[dict]):
    doc_file = _STORE_DIR / "documents.pkl"
    with open(doc_file, "wb") as f:
        pickle.dump(docs, f)


def _load_docs() -> list[dict]:
    doc_file = _STORE_DIR / "documents.pkl"
    if doc_file.exists():
        with open(doc_file, "rb") as f:
            return pickle.load(f)
    return []


def add_vectors(vectors: list[list[float]], documents: list[dict]):
    """
    添加向量及对应文档到共享知识库

    Args:
        vectors: [[0.1, 0.2, ...], ...]
        documents: [{"id": 1, "content": "...", "source": "..."}, ...]
    """
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


def search(query_vec: list[float], top_k: int = 5) -> list[dict]:
    """
    从共享知识库检索最相似的 top_k 个文档

    Args:
        query_vec: 查询向量
        top_k: 返回文档数

    Returns:
        [{"score": 0.95, "id": 0, "content": "...", "source": "..."}, ...]
    """
    index = _get_index()
    if index.ntotal == 0:
        return []

    arr = np.array([query_vec], dtype=np.float32)
    faiss.normalize_L2(arr)
    scores, indices = index.search(arr, top_k)

    docs = _load_docs()
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue
        doc = docs[idx]
        results.append({"score": round(float(score), 4), **doc})

    return results


def count() -> int:
    """共享索引中的文档总数"""
    return _get_index().ntotal


def remove_by_source(source: str) -> int:
    """
    按 source（文件名）删除文档的所有向量块
    """
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

    return removed


def clear():
    """清空共享索引"""
    import shutil as _su
    _su.rmtree(_STORE_DIR, ignore_errors=True)
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
