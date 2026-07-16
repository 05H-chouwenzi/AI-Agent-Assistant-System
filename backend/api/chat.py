"""聊天接口（异步版）—— 统一走循环图

完全匹配 ai-agent 架构：
- 使用 LangChain 消息格式
- result["messages"][-1] 提取最终回答
"""
import asyncio
import time
from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter(prefix="/api/chat", tags=["聊天"])

_DEFAULT_TITLE = "新对话"


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    conversation_id: int = 0


class ChatResponse(BaseModel):
    """聊天响应"""
    question: str
    task_type: str
    final_answer: str


async def _load_history_messages(conv_id: int, user_id: int) -> list:
    """异步加载会话历史，转为 LangChain 消息列表"""
    if conv_id <= 0:
        return []
    async with AsyncSessionLocal() as db:
        conv = await get_conversation(db, conv_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        past = (await get_conversation_messages(db, conv_id))[-20:]  # 只取最近 20 条
        messages = []
        for m in past:
            if m.role == "user":
                messages.append(HumanMessage(content=m.content))
            elif m.role == "assistant":
                messages.append(AIMessage(content=m.content))
        return messages


async def _save_messages(conv_id: int, question: str, answer: str, user_id: int, tenant_id: int | None):
    """异步保存消息到数据库"""
    if conv_id <= 0:
        return
    async with AsyncSessionLocal() as db:
        await create_message(db, conv_id, "user", question)
        await create_message(db, conv_id, "assistant", answer)
        conv = await get_conversation(db, conv_id, user_id)
        if conv and (not conv.title or conv.title == _DEFAULT_TITLE or len(conv.title) < 2):
            await update_conversation_title(db, conv_id, question[:30], user_id)


def _infer_task_type(state: AgentState) -> str:
    """从 state 推断任务类型（用于日志）"""
    route = state.get("route_history", [])
    if route:
        return "graph:" + "+".join(route)
    return "direct"


@router.post("/send", response_model=ChatResponse)
async def chat_send(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    _tenant_ok: User = Depends(require_tenant_access),
):
    """用户发送消息 → 统一循环图处理 → 返回结果"""
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # ========== FastRouter 旁路：零 LLM 调用处理简单请求 ==========
    _fast_router = FastRouter()
    _match = _fast_router.route(question)
    if _match and _match.is_final:
        register_default_tools()
        _manager = get_tool_manager()
        _result = await _manager.aexecute(_match.tool_name, **_match.tool_args)
        _fast_response = format_tool_result(_result, _match.tool_name)
        response_data = {
            "question": question,
            "task_type": "fast_router",
            "final_answer": _fast_response,
        }
        asyncio.create_task(async_log_chat_question(
            user_id=current_user.id, question=question,
            task_type="fast_router", is_stream=False,
            conversation_id=req.conversation_id or None,
            elapsed_ms=0, answer=_fast_response,
        ))
        await _save_messages(
            req.conversation_id, question, _fast_response,
            current_user.id, current_user.tenant_id,
        )
        return ChatResponse(**response_data)

    history_messages = await _load_history_messages(req.conversation_id, current_user.id)
    start = time.time()
    elapsed_ms = 0

    try:
        # 构建新格式 state：使用 LangChain 消息
        state = AgentState(
            messages=[*history_messages, HumanMessage(content=question)],
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            next_agent="",
            route_history=[],
            step_count=0,
            last_worker="",
        )

        result = await agent_graph.ainvoke(state)

        elapsed_ms = int((time.time() - start) * 1000)

        # 从 messages 中提取最后一条 AI 消息作为最终回答
        last_msg = result["messages"][-1]
        if isinstance(last_msg, AIMessage):
            final_answer = last_msg.content if isinstance(last_msg.content, str) else str(last_msg.content)
        else:
            final_answer = str(last_msg.content) if hasattr(last_msg, "content") else str(last_msg)

        task_type = _infer_task_type(result)

        if not final_answer:
            logger.warning(f"Graph 未产出 final_answer, question={question[:50]}")
            final_answer = "抱歉，我暂时无法回答这个问题。"

        response_data = {
            "question": question,
            "task_type": task_type,
            "final_answer": final_answer,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"chat_send 异常: {e}", exc_info=True)
        response_data = {
            "question": question,
            "task_type": "error",
            "final_answer": f"系统错误：{str(e)}",
        }

    # Fire-and-forget 操作日志
    asyncio.create_task(async_log_chat_question(
        user_id=current_user.id,
        question=question,
        task_type=response_data.get("task_type", "unknown"),
        is_stream=False,
        conversation_id=req.conversation_id or None,
        elapsed_ms=elapsed_ms,
        answer=response_data.get("final_answer", ""),
    ))

    await _save_messages(
        req.conversation_id, question,
        response_data.get("final_answer", ""),
        current_user.id, current_user.tenant_id,
    )

    return ChatResponse(**response_data)
