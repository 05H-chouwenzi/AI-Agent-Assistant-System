"""
Direct LLM —— 单次流式 LLM 调用（匹配 ai-qa-community 架构）

流程协议：
  FastRouter（规则匹配，零 LLM）
    │              │
   命中             未命中（↓ 此模块）
    │               │
    Tool        单次 LLM 流式调用（stream=True）
    │            （保持历史上下文 + 系统提示）
    │               │
   返回           SSE 流式输出
                    │
                存数据库

AI 决策路线图：
  单条系统提示词描述可用的工具能力 → LLM 自行决定是否需要调工具 → 流式返回
  无多 Agent 路由、无 Supervisor、无多轮 LLM 调用
"""
import json
from openai import AsyncOpenAI
from config.settings import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL

_client = AsyncOpenAI(
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    timeout=30.0,
    max_retries=1,
)

SYSTEM_PROMPT = """你是一个专业、清晰、简洁的企业 AI 助手。规则：
1. 直接回答用户问题，用中文
2. 如果需要实时数据（天气、汇率、计算等），用提供的工具
3. 如需查询企业内部知识或数据库，用提供的工具
4. 只采用真实信息，不编造数据
5. 回答保持简洁专业，适当分段"""


async def stream_llm(
    messages: list[dict],
    stream_queue=None,
    system_prompt: str | None = None,
) -> str:
    """单次 LLM 流式调用

    匹配 ai-qa-community 架构：
    - 单次调用，无多轮路由
    - stream=True 逐 token 推送
    - 返回完整文本

    Args:
        messages: [{"role": "user"/"assistant", "content": "..."}]
        stream_queue: 可选异步队列，推送 {"type": "token", "content": "..."}
        system_prompt: 可选覆盖默认系统提示

    Returns:
        完整回复内容
    """
    full_messages = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
    ] + messages[-20:]

    stream = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=full_messages,
        temperature=0.7,
        stream=True,
        stream_options={"include_usage": True},
    )

    full_content = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_content += token
            if stream_queue is not None:
                await stream_queue.put({"type": "token", "content": token})

    return full_content


async def call_llm(
    messages: list[dict],
    system_prompt: str | None = None,
) -> str:
    """非流式单次 LLM 调用（用于非流式端点）

    Args:
        messages: [{"role": "user"/"assistant", "content": "..."}]
        system_prompt: 可选覆盖默认系统提示

    Returns:
        LLM 回复内容
    """
    full_messages = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
    ] + messages[-20:]

    response = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=full_messages,
        temperature=0.1,
    )

    return response.choices[0].message.content or ""
