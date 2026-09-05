"""WebSocket 聊天 —— 统一走循环图（简化版，去掉了工具状态推送）"""
import json
import asyncio
import logging
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from langchain_core.messages import AIMessage, HumanMessage
from database.async_session import AsyncSessionLocal
from database.async_crud import (
    get_conversation, create_conversation,
    get_conversation_messages, create_message,
    update_conversation_title, get_user_by_id,
)
from agent.workflow.graph import agent_graph
from agent.graph.state import AgentState
from utils.auth import decode_access_token
from agent.graph.router import AGENT_LABELS
from agent.nodes.fast_router import FastRouter
from tools.tool_manager import get_tool_manager, register_default_tools
from tools.formatter import format_tool_result

logger = logging.getLogger(__name__)
_metrics_logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["WebSocket"])
_DEFAULT_TITLE = "新对话"
_HEARTBEAT_INTERVAL = 30


def _elapsed_ms(start_ns: int | None, end_ns: int | None) -> float | None:
    if start_ns is None or end_ns is None:
        return None
    return (end_ns - start_ns) / 1_000_000


async def _get_user_from_token(token: str):
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        return None
    async with AsyncSessionLocal() as db:
        return await get_user_by_id(db, user_id)


@router.websocket("/api/ws/chat/{conversation_id}")
async def chat_websocket(
    websocket: WebSocket, conversation_id: int, token: str = Query(...),
):
    user = await _get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await websocket.accept()

    async with AsyncSessionLocal() as db:
        if conversation_id == 0:
            conv = await create_conversation(db, _DEFAULT_TITLE, user.id, user.tenant_id)
            conversation_id = conv.id

    heartbeat_task = None

    async def _heartbeat():
        try:
            while True:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    try:
        heartbeat_task = asyncio.create_task(_heartbeat())

        while True:
            raw = await websocket.receive_text()
            t0 = time.perf_counter_ns()
            data = json.loads(raw)
            user_message = data.get("message", "").strip()
            if not user_message:
                continue

            # ========== FastRouter 旁路：零 LLM 调用处理简单请求（与 /send、/stream 一致）==========
            _fast_router = FastRouter()
            _match = _fast_router.route(user_message)
            fast_router_end = time.perf_counter_ns()
            if _match and _match.is_final:
                register_default_tools()
                _manager = get_tool_manager()
                _result = await _manager.aexecute(_match.tool_name, **_match.tool_args)
                _fast_response = format_tool_result(_result, _match.tool_name)
                async with AsyncSessionLocal() as db:
                    await create_message(db, conversation_id, "user", user_message)
                    await create_message(db, conversation_id, "assistant", _fast_response)
                    conv = await get_conversation(db, conversation_id, user.id)
                    if conv and (not conv.title or conv.title == _DEFAULT_TITLE):
                        await update_conversation_title(db, conversation_id, user_message[:30], user.id)
                        await websocket.send_json({"type": "title_update", "title": user_message[:30]})
                await websocket.send_json({"type": "token", "content": _fast_response})
                await websocket.send_json({"type": "done", "content": _fast_response, "conversation_id": conversation_id})
                continue

            # 先加载历史消息（不包含当前消息），避免重复
            async with AsyncSessionLocal() as db:
                past = await get_conversation_messages(db, conversation_id)
                t1 = time.perf_counter_ns()
            history_messages = []
            for m in past:
                if m.role == "user":
                    history_messages.append(HumanMessage(content=m.content))
                elif m.role == "assistant":
                    history_messages.append(AIMessage(content=m.content))

            async with AsyncSessionLocal() as db:
                await create_message(db, conversation_id, "user", user_message)
                t2 = time.perf_counter_ns()
                title_db_start = t2
                conv = await get_conversation(db, conversation_id, user.id)
                if conv and (not conv.title or conv.title == _DEFAULT_TITLE):
                    await update_conversation_title(db, conversation_id, user_message[:30], user.id)
                    title_db_end = time.perf_counter_ns()
                    await websocket.send_json({"type": "title_update", "title": user_message[:30]})
                else:
                    title_db_end = title_db_start

            state = AgentState(
                messages=[*history_messages, HumanMessage(content=user_message)],
                tenant_id=user.tenant_id,
                user_id=user.id,
                next_agent="",
                route_history=[],
                step_count=0,
                last_worker="",
            )

            full_answer = ""
            route_trail: list[str] = []
            stream_error = None
            t3 = time.perf_counter_ns()
            t4 = None
            t5 = None
            t6 = None
            t7 = None
            first_llm_node = ""
            first_token_node = ""
            first_token_len = 0
            first_token_send_ms = None
            token_receive_times_ns: list[int] = []
            token_send_complete_times_ns: list[int] = []
            token_event_intervals_ms: list[float] = []
            token_send_intervals_ms: list[float] = []
            stream_chunk_index = 0
            last_stream_chunk_at: int | None = None
            debug_logged = [False]

            def _log_ttft_debug(path: str) -> None:
                if debug_logged[0]:
                    return
                debug_logged[0] = True
                db_read_ms = _elapsed_ms(t0, t1)
                user_save_ms = _elapsed_ms(t1, t2)
                title_db_ms = _elapsed_ms(title_db_start, title_db_end)
                db_time = sum(
                    value for value in (db_read_ms, user_save_ms, title_db_ms)
                    if value is not None
                )
                token_intervals = ",".join(f"{value:.2f}" for value in token_event_intervals_ms)
                send_intervals = ",".join(f"{value:.2f}" for value in token_send_intervals_ms)
                _metrics_logger.info(
                    "\n[TTFT_DEBUG]\n"
                    "path=%s question_len=%d conversation_id=%d\n"
                    "total_pre_graph=%.2fms\n"
                    "db_time=%.2fms (history=%.2fms, save_user=%.2fms, title_db=%.2fms)\n"
                    "fast_router=%.2fms\n"
                    "first_llm_start=%.2fms node=%s\n"
                    "llm_ttft=%.2fms\n"
                    "first_token_total=%.2fms node=%s\n"
                    "first_send=%.2fms send_duration=%.2fms\n"
                    "first_token_content_len=%d\n"
                    "second_token_total=%.2fms first_to_second_token=%.2fms\n"
                    "first_10_token_intervals_ms=[%s]\n"
                    "first_10_send_intervals_ms=[%s]",
                    path,
                    len(user_message),
                    conversation_id,
                    (_elapsed_ms(t0, t3) or 0.0),
                    db_time,
                    (db_read_ms or 0.0),
                    (user_save_ms or 0.0),
                    (title_db_ms or 0.0),
                    (_elapsed_ms(t0, fast_router_end) or 0.0),
                    (_elapsed_ms(t3, t4) if t4 is not None else 0.0),
                    first_llm_node,
                    (_elapsed_ms(t4, t5) if t4 is not None and t5 is not None else 0.0),
                    (_elapsed_ms(t0, t5) if t5 is not None else 0.0),
                    first_token_node,
                    (_elapsed_ms(t0, t6) if t6 is not None else 0.0),
                    (first_token_send_ms or 0.0),
                    first_token_len,
                    (_elapsed_ms(t0, t7) if t7 is not None else 0.0),
                    (_elapsed_ms(t6, t7) if t6 is not None and t7 is not None else 0.0),
                    token_intervals,
                    send_intervals,
                )

            try:
                async for event in agent_graph.astream_events(state, version="v2"):
                    kind = event.get("event")
                    metadata = event.get("metadata")
                    node = metadata.get("langgraph_node", "") if isinstance(metadata, dict) else ""

                    if kind == "on_chat_model_start" and t4 is None:
                        t4 = time.perf_counter_ns()
                        first_llm_node = node

                    # Supervisor 路由事件（supervisor 完成后推送当前 Agent 信息）
                    if kind == "on_chain_end" and node == "supervisor":
                        data = event.get("data")
                        if isinstance(data, dict):
                            output = data.get("output") or {}
                        else:
                            output = {}
                        if isinstance(output, dict):
                            agent = output.get("next_agent", "")
                        else:
                            agent = ""
                        if agent and agent not in ("FINISH", "finish"):
                            label = AGENT_LABELS.get(agent, agent)
                            route_trail.append(agent)
                            await websocket.send_json({
                                "type": "route",
                                "agent": agent,
                                "label": label,
                                "trail": route_trail.copy(),
                            })

                    # Token 流式推送 — 跳过 supervisor 的 token
                    if kind == "on_chat_model_stream":
                        data = event.get("data")
                        chunk = data.get("chunk") if isinstance(data, dict) else None
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            stream_chunk_index += 1
                            stream_chunk_at = time.perf_counter_ns()
                            stream_interval_ms = (
                                0.0
                                if last_stream_chunk_at is None
                                else (stream_chunk_at - last_stream_chunk_at) / 1_000_000
                            )
                            if stream_chunk_index <= 20:
                                _metrics_logger.info(
                                    "\n[STREAM_DEBUG]\n"
                                    "chunk=%d\n"
                                    "llm_chunk_time=%.3f\n"
                                    "llm_interval=%.3fms\n"
                                    "content_len=%d",
                                    stream_chunk_index,
                                    time.time_ns() / 1_000_000,
                                    stream_interval_ms,
                                    len(chunk.content if isinstance(chunk.content, str) else str(chunk.content)),
                                )
                            last_stream_chunk_at = stream_chunk_at

                            if node == "supervisor":
                                continue
                            token_received_at = stream_chunk_at
                            if t5 is None:
                                t5 = token_received_at
                                first_token_node = node
                                first_token_len = len(
                                    chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                                )
                            elif len(token_receive_times_ns) <= 10:
                                previous = token_receive_times_ns[-1]
                                token_event_intervals_ms.append(
                                    (token_received_at - previous) / 1_000_000
                                )
                            token_receive_times_ns.append(token_received_at)

                            full_answer += chunk.content
                            first_token_send_start = token_received_at if t6 is None else None
                            ws_send_start = time.perf_counter_ns()
                            await websocket.send_json({"type": "token", "content": chunk.content})
                            token_sent_at = time.perf_counter_ns()
                            if stream_chunk_index <= 20:
                                _metrics_logger.info(
                                    "[STREAM_DEBUG] chunk=%d llm_chunk_to_ws_send_start=%.3fms ws_send_duration=%.3fms",
                                    stream_chunk_index,
                                    (ws_send_start - token_received_at) / 1_000_000,
                                    (token_sent_at - ws_send_start) / 1_000_000,
                                )
                            if first_token_send_start is not None:
                                t6 = token_sent_at
                                first_token_send_ms = (token_sent_at - first_token_send_start) / 1_000_000
                            if t7 is None and len(token_send_complete_times_ns) == 1:
                                t7 = token_sent_at
                            if token_send_complete_times_ns and len(token_send_complete_times_ns) <= 10:
                                previous_sent = token_send_complete_times_ns[-1]
                                token_send_intervals_ms.append(
                                    (token_sent_at - previous_sent) / 1_000_000
                                )
                            token_send_complete_times_ns.append(token_sent_at)

                    # 工具调用事件（可选，便于前端展示"正在查询..."）
                    elif kind == "on_tool_start":
                        data = event.get("data")
                        await websocket.send_json({
                            "type": "tool_start",
                            "tool": event.get("name"),
                            "input": data.get("input") if isinstance(data, dict) else None,
                        })
                    elif kind == "on_tool_end":
                        data = event.get("data")
                        await websocket.send_json({
                            "type": "tool_end",
                            "tool": event.get("name"),
                            "output": str(data.get("output", "") if isinstance(data, dict) else "")[:500],
                        })
            except Exception as e:
                logger.exception("Agent graph streaming error")
                stream_error = str(e)

            # Fallback：流式失败时用非流式获取完整回答（不再双重执行）
            if not full_answer and not stream_error:
                try:
                    result = await agent_graph.ainvoke(state)
                    last = result["messages"][-1]
                    if isinstance(last, AIMessage):
                        full_answer = last.content if isinstance(last.content, str) else str(last.content)
                        await websocket.send_json({"type": "token", "content": full_answer})
                except Exception as e:
                    logger.error("Agent graph ainvoke fallback error: %s", e)
                    if not full_answer:
                        full_answer = "抱歉，AI 服务暂时不可用。请稍后重试。"
                        await websocket.send_json({"type": "token", "content": full_answer})

            if not full_answer:
                full_answer = "抱歉，我暂时无法回答这个问题。"

            async with AsyncSessionLocal() as db:
                await create_message(db, conversation_id, "assistant", full_answer)

            await websocket.send_json({
                "type": "done",
                "content": full_answer,
                "conversation_id": conversation_id,
                "route_trail": route_trail,
            })
            _log_ttft_debug("agent_graph")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: conv={conversation_id}, user={user.id}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": "Connection error"})
        except Exception:
            pass
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
