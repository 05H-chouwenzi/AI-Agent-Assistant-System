"""
LLM 服务 —— 调用阿里云通义千问
"""
from openai import OpenAI
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL

client=OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)

def call_llm(system_prompt: str, user_message: str) -> str:
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content


def stream_llm(system_prompt: str, user_message: str):
    """流式调用 LLM，逐个 yield 文本块"""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        stream=True,
    )
    for chunk in response:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content