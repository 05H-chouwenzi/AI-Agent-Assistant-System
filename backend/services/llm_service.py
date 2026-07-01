"""
LLM 服务 —— 调用阿里云通义千问（支持 function calling & 流式）
"""
import time
from typing import Optional
from openai import OpenAI
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL

client = OpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
)


def call_llm(system_prompt: str, user_message: str, history: list | None = None) -> str:
    """标准 LLM 调用，返回完整文本"""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content


def stream_llm(
    system_prompt: str,
    user_message: str,
    history: list | None = None,
    force_char_level: bool = False,
    char_delay: float = 0.02,
):
    """
    流式调用 LLM，逐个 yield 文本块

    ★ 双模式设计（解决「非流式」问题）：
      模式1（force_char_level=False，默认）：
          使用 OpenAI SDK 原生 streaming，yield 每个 API chunk
          如果 LLM API 不支持真正的流式，chunk 会很大，前端感知不到逐字效果

      模式2（force_char_level=True）：
          先完整获取 LLM 回复，再按字符粒度 yield 并加入微小延迟
          保证前端看到逐字/逐小段输出，适合演示或调试

    在 chat_stream.py 中可通过 force_char_level=True 启用字符级模式
    """
    if force_char_level:
        # === 模式2：先获取完整回复，再字符级输出 ===
        full_text = call_llm(system_prompt, user_message, history=history)
        # 以 2-4 字为一组输出，避免单字输出太慢
        i = 0
        while i < len(full_text):
            # 取 2-4 个字（遇到标点可切短一些）
            chunk_size = 2
            if i + 3 <= len(full_text):
                chunk_size = 3
            if i + 4 <= len(full_text):
                chunk_size = 4
            # 如果当前字符是标点，只输出 1 个
            if full_text[i] in "，。！？、；：""''）】\n":
                chunk_size = 2
            chunk = full_text[i:i + chunk_size]
            i += chunk_size
            yield chunk
            time.sleep(char_delay)
    else:
        # === 模式1：原生 API 流式 ===
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


def call_llm_with_tools(
    system_prompt: str,
    user_message: str,
    tools: list[dict],
    history: list | None = None,
    temperature: float = 0.1,
    tool_choice: str = "auto",
) -> dict:
    """
    带 function calling 的 LLM 调用

    参数:
        system_prompt: 系统提示词
        user_message: 用户消息
        tools: OpenAI function calling 格式的工具列表
        history: 对话历史
        temperature: 温度（路由场景建议用低温度）
        tool_choice: "auto" 让 LLM 自动决定，或 "none" 禁用，或指定工具名

    返回:
        {
            "content": str | None,          # LLM 文本回复
            "tool_calls": list[dict] | None, # 工具调用列表
            "finish_reason": str,
        }
    """
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
    )

    choice = response.choices[0]
    msg = choice.message

    result = {
        "content": msg.content,
        "tool_calls": None,
        "finish_reason": choice.finish_reason,
    }

    if msg.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]

    return result