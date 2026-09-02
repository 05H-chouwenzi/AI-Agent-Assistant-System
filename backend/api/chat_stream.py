"""聊天流式接口 (SSE 推送) —— 真正的 LLM Token Streaming

采用 LangGraph astream_events() + AIMessageChunk 实现真正的 token-level streaming
"""
import asyncio
import json
import time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from database.async_session import AsyncSessionLocal
from database.async_crud import (
    get_conversation, create_conversation,
    get_conversation_messages, create_message,
    update_conversation_title,
)
from models.user import User
from utils.auth import get_current_user, require_tenant_access
from agent.workflow.graph import agent_graph
from agent.graph.state import AgentState
from agent.nodes.fast_router import FastRouter
from tools.tool_manager import get_tool_manager, register_default_tools
from tools.formatter import format_tool_result
from logs.operation_logger import async_log_chat_question
from logs.logger import logger
import re


def _strip_md(text: str) -> str:
    """Remove Markdown symbols from text"""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|', '', text)
    text = re.sub(r'^>', '', text, flags=re.MULTILINE)
    text = re.sub(r'^-{3,}', '', text, flags=re.MULTILINE)
    return text


router = APIRouter(prefix="/api/chat", tags=["聊天"])
_DEFAULT_TITLE = "新对话"


class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0


def sse_event(event_type: str, content, ensure_ascii=False) -> str:
    data = {'type': event_type, 'content': content}
    return f"data: {json.dumps(data, ensure_ascii=ensure_ascii)}\n\n"


@router.post("/stream")
async def chat_stream(
    req: ChatStreamRequest,
    user: User = Depends(get_current_user),
    _tenant_ok: User = Depends(require_tenant_access),
):
    question = req.question.strip()
    if not question:
        return StreamingResponse(sse_event("error", "消息不能为空"), media_type="text/event-stream")

    async def event_stream():
        stream_start = time.time()
        try:
            yield sse_event("start", {"question": question[:50]})

            # FastRouter 旁路
            _fast_router = FastRouter()
            _match = _fast_router.route(question)
            if _match and _match.is_final:
                register_default_tools()
                _manager = get_tool_manager()
                _result = await _manager.aexecute(_match.tool_name, **_match.tool_args)
                _fast_response = format_tool_result(_result, _match.tool_name)
                yield sse_event("chunk", _fast_response)
                yield sse_event("done", {"content": _fast_response, "conversation_id": req.conversation_id})
                return

            conv_id = req.conversation_id
            async with AsyncSessionLocal() as db:
                if not conv_id or conv_id == 0:
                    conv = await create_conversation(db, question[:30], user.id, user.tenant_id)
                    conv_id = conv.id
                past = (await get_conversation_messages(db, conv_id))[-20:] if conv_id > 0 else []
                await create_message(db, conv_id, "user", question)

            history_messages = []
            for m in past:
                if m.role == "user":
                    history_messages.append(HumanMessage(content=m.content))
                elif m.role == "assistant":
                    history_messages.append(AIMessage(content=m.content))

            state = AgentState(
                messages=[*history_messages, HumanMessage(content=question)],
                tenant_id=user.tenant_id, user_id=user.id,
                next_agent="", route_history=[], step_count=0, last_worker="",
            )

            full_answer = ""
            
            # ========== 真正的 Token Streaming using astream_events() ==========
            # LangGraph v0.2+ 支持通过 events 流式传递 LLM token
            # 监听 on_llm_new_token 事件来获取真正的 token 流
            
            async for event in agent_graph.astream_events(
                state, 
                config={"recursion_limit": 20},
                version="v2"
            ):
                kind = event.get("event")
                
                # 监听 LLM token 生成事件 (真正的 token-level streaming)
                if kind == "on_llm_new_token":
                    data = event.get("data", {})
                    token = data.get("token", "")
                    
                    if token:
                        cleaned = _strip_md(token)
                        new_chunk = cleaned[len(full_answer):] if len(cleaned) > len(full_answer) else ""
                        if new_chunk:
                            full_answer = cleaned
                            yield sse_event("chunk", new_chunk)
                
                # 同时也监听 on_chain_end 来捕获完整消息作为兜底
                elif kind == "on_chain_end":
                    data = event.get("data", {})
                    output = data.get("output", None)
                    
                    if output and hasattr(output, "get"):
                        messages = output.get("messages", [])
                        for msg in reversed(messages):
                            if isinstance(msg, AIMessage):
                                msg_content = msg.content if isinstance(msg.content, str) else str(msg.content)
                                if msg_content:
                                    cleaned = _strip_md(msg_content)
                                    new_chunk = cleaned[len(full_answer):] if len(cleaned) > len(full_answer) else ""
                                    if new_chunk:
                                        full_answer = cleaned
                                        yield sse_event("chunk", new_chunk)

            # 兜底：如果仍为空
            if not full_answer:
                full_answer = "抱歉，我暂时无法回答这个问题。"

            elapsed_ms = int((time.time() - stream_start) * 1000)
            task_type = "direct"

            asyncio.create_task(async_log_chat_question(
                user_id=user.id, question=question,
                task_type=task_type, is_stream=True,
                conversation_id=conv_id, elapsed_ms=elapsed_ms, answer=full_answer,
            ))

            async with AsyncSessionLocal() as db:
                await create_message(db, conv_id, "assistant", full_answer)
                conv = await get_conversation(db, conv_id, user.id)
                if conv and (not conv.title or conv.title == _DEFAULT_TITLE):
                    await update_conversation_title(db, conv_id, question[:30], user.id)

            yield sse_event("done", {"content": full_answer, "conversation_id": conv_id})

        except Exception as e:
            logger.error(f"chat_stream 异常:{e}", exc_info=True)
            yield sse_event("error", f"系统错误:{str(e)}")

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )
