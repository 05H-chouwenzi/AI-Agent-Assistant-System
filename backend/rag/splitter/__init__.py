"""
文本分割器 —— 将长文档切块
"""
CHUNK_SIZE = 500        # 每块字符数
CHUNK_OVERLAP = 50      # 相邻块重叠字符数


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """将文本按大小切块，支持重叠"""
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
