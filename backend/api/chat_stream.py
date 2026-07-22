"""聊天流式接口（SSE 推送）—— 统一走循环图"""
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
from agent.graph.router import AGENT_LABELS
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
    text = re.sub(r':', '', text)
    return text

router = APIRouter(prefix="/api/chat", tags=["聊天"])
_DEFAULT_TITLE = "新对话"

class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0

def sse_event(event_type: str, content, ensure_ascii=False) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=ensure_ascii)}\n\n"

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
            # ========== FastRouter 旁路：零 LLM 调用处理简单请求 ==========
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
                past = (await get_conversation_messages(db, conv_id))[-20:]  # 只取最近 20 条 if conv_id > 0 else []
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
            graph_events_received = False
            async for event in agent_graph.astream_events(state, version="v2"):
                graph_events_received = True
                kind = event.get("event")
                metadata = event.get("metadata")
                node = metadata.get("langgraph_node", "") if isinstance(metadata, dict) else ""

                # Token 流 — 只流 worker 的 token，跳过 supervisor
                if kind == "on_chat_model_stream":
                    data = event.get("data")
                    chunk = data.get("chunk") if isinstance(data, dict) else None
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        # Worker token 直接流出，不再过滤（工作流已简化为 Worker→END，无多余 LLM 调用）
                        cleaned = _strip_md(chunk.content)
                        if cleaned:
                            full_answer += cleaned
                            yield sse_event("chunk", cleaned)

            # Fallback: 仅在流式 API 完全失败（零事件）时才走非流式
            # 正常情况即使回答为空也不会触发此分支，避免双重 LLM 调用
            if not graph_events_received:
                result = await agent_graph.ainvoke(state)
                last = result["messages"][-1]
                if isinstance(last, AIMessage):
                    full_answer = last.content if isinstance(last.content, str) else str(last.content)
                    yield sse_event("chunk", full_answer)

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
            logger.error(f"chat_stream 异常: {e}", exc_info=True)
            yield sse_event("error", f"系统错误：{str(e)}")

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )
