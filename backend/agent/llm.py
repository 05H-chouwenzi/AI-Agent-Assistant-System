"""LangChain LLM 配置 —— 统一 LLM 获取入口（缓存实例，避免每次重建）

支持智谱 GLM、DeepSeek、DashScope 等 OpenAI 兼容 API。
通过 .env 中的 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 配置。
"""
from langchain_openai import ChatOpenAI
from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    VISION_LLM_API_KEY,
    VISION_LLM_BASE_URL,
    VISION_LLM_MODEL,
)

_llm_instance: ChatOpenAI | None = None
_llm_streaming_instance: ChatOpenAI | None = None
_vision_llm_instance: ChatOpenAI | None = None
_vision_llm_streaming_instance: ChatOpenAI | None = None


def get_llm(*, streaming: bool = True) -> ChatOpenAI:
    """获取 LangChain ChatOpenAI 实例（缓存复用，避免每次重建）

    支持智谱 GLM、DeepSeek、DashScope 等任何 OpenAI 兼容 API。
    Args:
        streaming: 是否启用流式输出
    Returns:
        ChatOpenAI 实例
    """
    global _llm_instance, _llm_streaming_instance

    if streaming:
        if _llm_streaming_instance is None:
            _llm_streaming_instance = ChatOpenAI(
                model=LLM_MODEL,
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                streaming=True,
                temperature=0.3,
            )
        return _llm_streaming_instance

    if _llm_instance is None:
        _llm_instance = ChatOpenAI(
            model=LLM_MODEL,
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            streaming=False,
            temperature=0.3,
        )
    return _llm_instance


def get_vision_llm(*, streaming: bool = True) -> ChatOpenAI:
    """Get the separate Vision-capable LLM used only when a message has images.

    DashScope's OpenAI-compatible endpoint is the default because the project
    already stores DASHSCOPE_API_KEY / DASHSCOPE_BASE_URL.
    """
    global _vision_llm_instance, _vision_llm_streaming_instance

    if not VISION_LLM_API_KEY:
        raise RuntimeError("当前未配置 Vision-capable model，请设置 VISION_LLM_API_KEY / VISION_LLM_MODEL")

    if streaming:
        if _vision_llm_streaming_instance is None:
            _vision_llm_streaming_instance = ChatOpenAI(
                model=VISION_LLM_MODEL,
                api_key=VISION_LLM_API_KEY,
                base_url=VISION_LLM_BASE_URL,
                streaming=True,
                temperature=0.3,
            )
        return _vision_llm_streaming_instance

    if _vision_llm_instance is None:
        _vision_llm_instance = ChatOpenAI(
            model=VISION_LLM_MODEL,
            api_key=VISION_LLM_API_KEY,
            base_url=VISION_LLM_BASE_URL,
            streaming=False,
            temperature=0.3,
        )
    return _vision_llm_instance
