"""
检索器 —— 用户问题 → 向量检索 → 返回文档（共享知识库）
"""
from rag.embedding import embed_text, aembed_text
from rag.vector_store import search


def retrieve(question: str, top_k: int = 5, user_id: int | None = None) -> list[dict]:
    """根据问题从共享知识库检索最相关的文档片段（同步版本）"""
    if user_id is None:
        return []
    vec = embed_text(question)
    return search(vec, top_k=top_k, user_id=user_id)


async def aretrieve(question: str, top_k: int = 5, user_id: int | None = None) -> list[dict]:
    """根据问题从共享知识库检索最相关的文档片段（异步版本）"""
    if user_id is None:
        return []
    vec = await aembed_text(question)
    return search(vec, top_k=top_k, user_id=user_id)
