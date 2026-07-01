"""
Embedding 模块 —— 用阿里云 Dashscope 文本向量化
"""
from openai import OpenAI
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)

def embed_text(text: str) -> list[float]:
    """将单段文本转为向量"""
    resp = client.embeddings.create(
        model="text-embedding-v3",
        input=text,
    )
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量将文本转为向量（自动分批，每批最多 10 条）"""
    BATCH_SIZE = 10
    all_embeddings = [None] * len(texts)

    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]
        resp = client.embeddings.create(
            model="text-embedding-v3",
            input=batch,
        )
        for item in resp.data:
            all_embeddings[start + item.index] = item.embedding

    return all_embeddings
