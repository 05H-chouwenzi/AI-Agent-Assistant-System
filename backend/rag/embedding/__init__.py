"""
Embedding 模块 —— 用阿里云 Dashscope 文本向量化
"""
from functools import lru_cache
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL


@lru_cache(maxsize=1)
def _get_client():
    """懒加载同步 OpenAI client（首次调用时才创建，避免导入时 4s 延迟）"""
    from openai import OpenAI
    return OpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
    )


@lru_cache(maxsize=1)
def _get_async_client():
    """懒加载异步 OpenAI client"""
    from openai import AsyncOpenAI
    return AsyncOpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url=DASHSCOPE_BASE_URL,
        timeout=30.0,
        max_retries=1,
    )

def embed_text(text: str) -> list[float]:
    """将单段文本转为向量（同步版本）"""
    resp = _get_client().embeddings.create(
        model="text-embedding-v3",
        input=text,
    )
    return resp.data[0].embedding

async def aembed_text(text: str) -> list[float]:
    """将单段文本转为向量（异步版本）"""
    resp = await _get_async_client().embeddings.create(
        model="text-embedding-v3",
        input=text,
    )
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转为向量（自动分批，每批最多 10 条）"""
    BATCH_SIZE = 10
    all_embeddings = [None] * len(texts)
    c = _get_client()

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        resp = c.embeddings.create(
            model="text-embedding-v3",
            input=batch,
        )
        for item in resp.data:
            all_embeddings[start + item.index] = item.embedding

    return all_embeddings
