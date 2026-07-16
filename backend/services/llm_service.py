"""
LLM 服务 —— 调用阿里云通义千问（支持 function calling & 流式）
"""
import json
import time
from typing import Optional
from openai import OpenAI
from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)


def _tool_call_to_dict(tc) -> dict:
    """将 OpenAI SDK tool_call 对象转为可序列化的字典"""
    return {
        "id": tc.id,
        "type": "function",
        "function": {
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        },
    }


def call_llm(
    system_prompt: str,
    user_message: str,
    history: list | None = None,
    tools: list | None = None,
) -> str:
    """
    标准 LLM 调用，支持 function calling。

    如果传入 tools 且 LLM 返回 tool_calls，会自动执行工具并重试。
    支持多轮 tool call（LLM 在收到工具结果后可能再调另一个工具）。
    """
    messages = _build_messages(system_prompt, user_message, history)

    max_rounds = 5  # 防止无限循环
    for _ in range(max_rounds):
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            tools=tools or [],
        )

        message = response.choices[0].message

        # ✅ 没有工具调用 → 直接返回文本
        if not message.tool_calls:
            return message.content or ""

        # 🔧 有工具调用 → 执行工具并追加结果
        assistant_msg = {"role": "assistant", "content": message.content}
        assistant_msg["tool_calls"] = [_tool_call_to_dict(tc) for tc in message.tool_calls]
        messages.append(assistant_msg)

        for tc in message.tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            # 执行工具
            from tools.tool_manager import get_tool_manager
            manager = get_tool_manager()
            result = manager.execute(tool_name, **tool_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result.to_message(),
            })

    # 超过最大轮次，返回最后的文本或提示
    return messages[-1].get("content", "抱歉，处理超时，请重试。")


def stream_llm(
    system_prompt: str,
    user_message: str,
    history: list | None = None,
    force_char_level: bool = False,
    char_delay: float = 0.02,
    tools: list | None = None,
):
    """
    流式调用 LLM，支持 function calling

    ★ 双模式设计：
      模式1（默认）：先非流式判断是否有工具调用 → 执行工具 → 再流式输出最终回答
      模式2（force_char_level=True）：先完整获取回复，再逐字输出
    """
    if force_char_level:
        full_text = call_llm(system_prompt, user_message, history=history, tools=tools)
        i = 0
        while i < len(full_text):
            chunk_size = 2
            if i + 3 <= len(full_text):
                chunk_size = 3
            if i + 4 <= len(full_text):
                chunk_size = 4
            if full_text[i] in "，。！？、；：""''）】\n":
                chunk_size = 2
            chunk = full_text[i:i + chunk_size]
            i += chunk_size
            yield chunk
            time.sleep(char_delay)
        return

    # === 模式1：标准流式（支持工具调用）===
    messages = _build_messages(system_prompt, user_message, history)

    # ---- 第1步：先非流式调用，判断是否有工具调用 ----
    if tools:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            tools=tools,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            # 追加 assistant 消息（包含 tool_calls）
            assistant_msg = {"role": "assistant", "content": msg.content}
            assistant_msg["tool_calls"] = [_tool_call_to_dict(tc) for tc in msg.tool_calls]
            messages.append(assistant_msg)

            # 执行所有工具并追加结果
            from tools.tool_manager import get_tool_manager
            manager = get_tool_manager()
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                result = manager.execute(tool_name, **tool_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.to_message(),
                })

    # ---- 第2步：流式输出最终回答（不传 tools，避免再调工具） ----
    stream = client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=0.7,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content


def _build_messages(
    system_prompt: str,
    user_message: str,
    history: list | None = None,
) -> list:
    """构建消息列表"""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages
