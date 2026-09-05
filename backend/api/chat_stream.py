"""聊天流式接口（SSE Token Stream）—— 统一走循环图"""
import asyncio
import json
import logging
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
from agent.monitor import PerformanceMonitor

router = APIRouter(prefix="/api/chat", tags=["聊天"])
_DEFAULT_TITLE = "新对话"
WORKER_NODES = {"research", "data", "general"}
VISIBLE_STREAM_NODES = WORKER_NODES | {"synthesize"}
_metrics_logger = logging.getLogger("uvicorn.error")


class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0


def sse_event(event_type: str, content, ensure_ascii=False) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=ensure_ascii)}\n\n"


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


_SSE_KEEPALIVE_INTERVAL_SECONDS = 15.0
_QUEUE_END = object()
_QUEUE_KEEPALIVE = object()


async def _iter_graph_events_with_keepalive(source, *, interval: float):
    """转发 LangGraph 事件，并在上游长时间无事件时插入 SSE keepalive 标记。"""
    queue: asyncio.Queue = asyncio.Queue()

    async def _produce_events():
        try:
            async for event in source:
                await queue.put(event)
        except Exception as exc:
            await queue.put(exc)
        finally:
            await queue.put(_QUEUE_END)

    async def _produce_keepalive():
        while True:
            await asyncio.sleep(interval)
            await queue.put(_QUEUE_KEEPALIVE)

    producer_task = asyncio.create_task(_produce_events())
    keepalive_task = asyncio.create_task(_produce_keepalive())
    try:
        while True:
            item = await queue.get()
            if item is _QUEUE_END:
                break
            if item is _QUEUE_KEEPALIVE:
                yield {"event": "__sse_keepalive__"}
                continue
            if isinstance(item, BaseException):
                raise item
            yield item
    finally:
        keepalive_task.cancel()
        producer_task.cancel()
        await asyncio.gather(keepalive_task, producer_task, return_exceptions=True)


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
        monitor = PerformanceMonitor()
        stream_started_perf_ns = time.perf_counter_ns()
        stream_started_epoch_ms = time.time_ns() // 1_000_000
        last_event_perf_ns = stream_started_perf_ns
        last_event_kind = ""
        last_event_node = ""
        try:
            # FastRouter 旁路：零 LLM 调用处理简单请求。
            fast_router_start = time.perf_counter_ns()
            _fast_router = FastRouter()
            _match = _fast_router.route(question)
            monitor.metrics.node_time_ms["fast_router"] += (
                time.perf_counter_ns() - fast_router_start
            ) / 1_000_000
            if _match and _match.is_final:
                register_default_tools()
                _manager = get_tool_manager()
                tool_start = time.perf_counter_ns()
                _result = await _manager.aexecute(_match.tool_name, **_match.tool_args)
                monitor.record_tool_duration(
                    _match.tool_name,
                    (time.perf_counter_ns() - tool_start) / 1_000_000,
                )
                _fast_response = format_tool_result(_result, _match.tool_name)
                monitor.record_first_user_visible_token("fast_router")
                yield sse_event("chunk", _fast_response)
                yield sse_event("done", {"content": _fast_response, "conversation_id": req.conversation_id})
                monitor.finish()
                _metrics_logger.info("\n%s", monitor.get_metrics())
                return

            conv_id = req.conversation_id
            async with AsyncSessionLocal() as db:
                if not conv_id or conv_id == 0:
                    conv = await create_conversation(db, question[:30], user.id, user.tenant_id)
                    conv_id = conv.id
                past = (await get_conversation_messages(db, conv_id))[-20:]
                await create_message(db, conv_id, "user", question)

            history_messages = []
            for m in past:
                if m.role == "user":
                    history_messages.append(HumanMessage(content=m.content))
                elif m.role == "assistant":
                    history_messages.append(AIMessage(content=m.content))

            state = AgentState(
                messages=[*history_messages, HumanMessage(content=question)],
                tenant_id=user.tenant_id,
                user_id=user.id,
                next_agent="",
                route_history=[],
                step_count=0,
                last_worker="",
            )

            full_answer = ""
            worker_answers: dict[str, str] = {}
            synthesize_started = False

            # LangGraph v2 事件流能把节点、模型 token 和工具调用区分开。
            source = agent_graph.astream_events(state, version="v2")
            _metrics_logger.info(
                "[SSE_STREAM_START] stream_start=%d question_len=%d conversation_id=%d",
                stream_started_epoch_ms,
                len(question),
                conv_id,
            )
            async for event in _iter_graph_events_with_keepalive(
                source,
                interval=_SSE_KEEPALIVE_INTERVAL_SECONDS,
            ):
                kind = event.get("event")
                if kind == "__sse_keepalive__":
                    yield ": keepalive\n\n"
                    continue

                metadata = event.get("metadata")
                node = metadata.get("langgraph_node", "") if isinstance(metadata, dict) else ""
                name = event.get("name", "")
                run_id = event.get("run_id", "")
                parent_ids = event.get("parent_ids", [])
                outer_node = monitor.resolve_node(node, parent_ids)
                last_event_perf_ns = time.perf_counter_ns()
                last_event_kind = kind
                last_event_node = outer_node or node or last_event_node

                if kind == "on_chain_start" and name == node:
                    monitor.record_node_start(run_id, node)
                    if node == "synthesize":
                        synthesize_started = True
                        # 多 Worker 场景：最终答案只保留 Synthesize 聚合结果。
                        full_answer = ""

                if kind == "on_chat_model_start":
                    monitor.record_llm_start(run_id, outer_node)

                if kind == "on_chat_model_end":
                    monitor.record_llm_end(run_id)

                if kind == "on_chat_model_stream" and outer_node in VISIBLE_STREAM_NODES:
                    data = event.get("data", {})
                    chunk = data.get("chunk") if isinstance(data, dict) else None
                    token = getattr(chunk, "content", "")
                    if isinstance(token, str) and token:
                        monitor.record_first_user_visible_token(outer_node)
                        if outer_node == "synthesize" and not synthesize_started:
                            synthesize_started = True
                            full_answer = ""
                        full_answer += token
                        yield sse_event("chunk", token)

                if kind == "on_tool_start":
                    monitor.record_tool_start(run_id, str(event.get("name", "unknown")), outer_node)
                elif kind == "on_tool_end":
                    monitor.record_tool_end(run_id)

                if kind == "on_chain_end" and name == node:
                    monitor.record_node_end(run_id, node)

                # 捕获 Worker 最终消息，供非流式 LLM 或零 token 场景使用。
                if kind == "on_chain_end" and node in WORKER_NODES:
                    data = event.get("data", {})
                    output = data.get("output", {}) if isinstance(data, dict) else {}
                    messages = output.get("messages", []) if isinstance(output, dict) else []
                    if messages:
                        text = _message_text(messages[-1])
                        if text:
                            worker_answers[node] = text

                if kind == "on_chain_end" and node == "synthesize":
                    data = event.get("data", {})
                    output = data.get("output", {}) if isinstance(data, dict) else {}
                    messages = output.get("messages", []) if isinstance(output, dict) else []
                    full_answer = _message_text(messages[-1]) if messages else ""
                    if not full_answer:
                        full_answer = "抱歉，我暂时无法回答这个问题。"

                if kind == "on_chain_end" and node == "supervisor":
                    data = event.get("data", {})
                    output = data.get("output", {}) if isinstance(data, dict) else {}
                    next_agent = output.get("next_agent", "") if isinstance(output, dict) else ""
                    if next_agent and next_agent != "FINISH":
                        monitor.record_route(next_agent)

            # 零 token 流时使用已捕获的 Worker 结果，不重复执行整个 Graph。
            if not full_answer:
                captured = next((text for text in reversed(worker_answers.values()) if text), "")
                full_answer = captured or "抱歉，我暂时无法回答这个问题。"
                monitor.record_first_user_visible_token("graph_fallback")
                yield sse_event("chunk", full_answer)

            if not full_answer:
                full_answer = "抱歉，我暂时无法回答这个问题。"

            asyncio.create_task(async_log_chat_question(
                user_id=user.id,
                question=question,
                task_type="direct",
                is_stream=True,
                conversation_id=conv_id,
                elapsed_ms=int(monitor.metrics.total_latency_ms),
                answer=full_answer,
            ))

            async with AsyncSessionLocal() as db:
                await create_message(db, conv_id, "assistant", full_answer)
                conv = await get_conversation(db, conv_id, user.id)
            if conv and (not conv.title or conv.title == _DEFAULT_TITLE):
                await update_conversation_title(db, conv_id, question[:30], user.id)

            yield sse_event("done", {"content": full_answer, "conversation_id": conv_id})
            monitor.finish()
            _metrics_logger.info("\n%s", monitor.get_metrics())

        except asyncio.CancelledError:
            now_ns = time.perf_counter_ns()
            _metrics_logger.warning(
                "[SSE_STREAM_CANCELLED] stream_start=%d elapsed_ms=%.1f "
                "last_event_age_ms=%.1f last_event_kind=%s last_event_node=%s "
                "question_len=%d",
                stream_started_epoch_ms,
                (now_ns - stream_started_perf_ns) / 1_000_000,
                (now_ns - last_event_perf_ns) / 1_000_000,
                last_event_kind or "N/A",
                last_event_node or "N/A",
                len(question),
            )
            raise
        except GeneratorExit:
            now_ns = time.perf_counter_ns()
            _metrics_logger.warning(
                "[SSE_STREAM_DISCONNECTED] stream_start=%d elapsed_ms=%.1f "
                "last_event_age_ms=%.1f last_event_kind=%s last_event_node=%s "
                "question_len=%d",
                stream_started_epoch_ms,
                (now_ns - stream_started_perf_ns) / 1_000_000,
                (now_ns - last_event_perf_ns) / 1_000_000,
                last_event_kind or "N/A",
                last_event_node or "N/A",
                len(question),
            )
            raise
        except Exception as e:
            logger.error(f"chat_stream 异常：{e}", exc_info=True)
            _metrics_logger.error(
                "[SSE_STREAM_ERROR] elapsed_ms=%.1f last_event_age_ms=%.1f "
                "last_event_kind=%s last_event_node=%s question_len=%d",
                (time.perf_counter_ns() - stream_started_perf_ns) / 1_000_000,
                (time.perf_counter_ns() - last_event_perf_ns) / 1_000_000,
                last_event_kind or "N/A",
                last_event_node or "N/A",
                len(question),
            )
            monitor.finish()
            _metrics_logger.info("\n%s", monitor.get_metrics())
            yield sse_event("error", f"系统错误：{str(e)}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, private",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )
