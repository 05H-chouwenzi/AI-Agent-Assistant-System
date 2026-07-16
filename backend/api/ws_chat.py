"""WebSocket 聊天 —— 统一走循环图（简化版，去掉了工具状态推送）"""
import json
import asyncio
import logging
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

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])
_DEFAULT_TITLE = "新对话"
_HEARTBEAT_INTERVAL = 30


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
    if not getattr(user, "tenant_id", None) and not getattr(user, "is_superuser", False):
        await websocket.close(code=4003, reason="No tenant access")
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
            data = json.loads(raw)
            user_message = data.get("message", "").strip()
            if not user_message:
                continue

            async with AsyncSessionLocal() as db:
                await create_message(db, conversation_id, "user", user_message)
                conv = await get_conversation(db, conversation_id, user.id)
                if conv and (not conv.title or conv.title == _DEFAULT_TITLE):
                    await update_conversation_title(db, conversation_id, user_message[:30], user.id)
                    await websocket.send_json({"type": "title_update", "title": user_message[:30]})

            # 加载历史消息（LangChain 格式）
            async with AsyncSessionLocal() as db:
                past = await get_conversation_messages(db, conversation_id)
            history_messages = []
            for m in past:
                if m.role == "user":
                    history_messages.append(HumanMessage(content=m.content))
                elif m.role == "assistant":
                    history_messages.append(AIMessage(content=m.content))

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

            try:
                async for event in agent_graph.astream_events(state, version="v2"):
                    kind = event.get("event")
                    metadata = event.get("metadata")
                    node = metadata.get("langgraph_node", "") if isinstance(metadata, dict) else ""

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
                            if node == "supervisor":
                                continue
                            full_answer += chunk.content
                            await websocket.send_json({"type": "token", "content": chunk.content})

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
