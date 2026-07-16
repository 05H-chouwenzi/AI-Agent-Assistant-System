"""异步 LLM 服务 —— 单次流式调用，在流过程中解析 tool_calls
去掉非流式预检，一次调完。"""
import json
from openai import AsyncOpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

_async_client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
    timeout=30.0,
    max_retries=1,
)


async def async_call_llm(
    system_prompt: str,
    messages: list[dict],
    tools: list | None = None,
) -> tuple[str, list[dict] | None]:
    """非流式调用 —— 给 Synthesize fallback 用，一次性返回"""
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    response = await _async_client.chat.completions.create(
        model=LLM_MODEL,
        messages=full_messages,
        temperature=0.1,
        tools=tools or [],
    )
    msg = response.choices[0].message

    tool_calls = None
    if msg.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]

    return msg.content or "", tool_calls


async def async_stream_with_tools(
    system_prompt: str,
    messages: list[dict],
    tools: list | None = None,
    stream_queue=None,
) -> tuple[str, list[dict] | None]:
    """
    单次流式调用 —— 不再预先非流式判断 tool_calls

    1. 直接开流
    2. 逐 token 推送到 stream_queue（如果有）
    3. 同时在流过程中累积 tool_calls
    4. 流结束，返回 (content, tool_calls)
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    stream = await _async_client.chat.completions.create(
        model=LLM_MODEL,
        messages=full_messages,
        temperature=0.7,
        tools=tools or [],
        stream=True,
        stream_options={"include_usage": True},
    )

    full_content = ""
    tool_calls_acc: dict[int, dict] = {}

    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        # 累积文本
        if delta and delta.content:
            full_content += delta.content
            if stream_queue is not None:
                await stream_queue.put({"type": "token", "content": delta.content})

        # 累积 tool_calls（DashScope 流式 tool_calls 模式）
        if delta and delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {
                        "id": tc.id or "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                entry = tool_calls_acc[idx]
                if tc.id:
                    entry["id"] = tc.id
                if tc.function:
                    if tc.function.name:
                        entry["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        entry["function"]["arguments"] += tc.function.arguments

    tool_calls_list = list(tool_calls_acc.values()) if tool_calls_acc else None
    return full_content, tool_calls_list
