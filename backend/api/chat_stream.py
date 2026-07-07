"""
聊天流式接口 —— SSE 逐字推送 + 完整多轮记忆（支持工具调用）

核心改进：
1. 每个处理阶段前 yield status 事件，让用户看到 AI "正在思考"
2. 支持 direct / rag / tool 三种任务类型的实时状态反馈
3. 参考「AI黑马项目」的 chain.stream 模式，先发状态再发数据
"""
import json
import time
import traceback
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.session import SessionLocal
from models.user import User
from utils.auth import get_current_user
from fastapi import HTTPException
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from services.llm_service import stream_llm
from logs.operation_logger import OperationLogger, Actions
from crud import conversation as conv_crud
from crud import message as msg_crud
from tools.tool_manager import get_tool_manager

router = APIRouter(prefix="/api/chat", tags=["聊天"])


class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0


def sse_event(event_type: str, content, ensure_ascii=False) -> str:
    """快速构造 SSE 事件 JSON 字符串"""
    return f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=ensure_ascii)}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatStreamRequest, user: User = Depends(get_current_user)):
    """
    流式：Planner → (RAG/Tool) → LLM → SSE 逐字返回 + 实时状态 + 保存消息 + 多轮记忆
    """
    def event_stream():
        """同步生成器：在 thread pool 中运行，每个 yield 立即推送"""
        db = SessionLocal()
        stream_start = time.time()
        try:
            # ========== 1. 会话初始化 ==========
            conv_id = req.conversation_id
            if not conv_id or conv_id == 0:
                conv = conv_crud.create_conversation(db, req.question[:30], user.id)
                conv_id = conv.id

            # 加载历史消息
            history = []
            if conv_id and conv_id > 0:
                conv = conv_crud.get_conversation(db, conv_id, user.id)
                if not conv:
                    yield sse_event("error", "对话不存在")
                    return

                past_messages = msg_crud.get_conversation_messages(db, conv_id)
                for m in past_messages:
                    history.append({"role": m.role, "content": m.content})

            # 用户消息入库
            msg_crud.create_message(db, conv_id, "user", req.question)
            db.commit()

            # ========== 2. 初始化状态 ==========
            state: AgentState = {
                "question": req.question,
                "history": history[-10:],
                "user_id": user.id,
            }

            # ========== 3-4. LangGraph Workflow（planner → rag/tool → prompt_builder）==========
            state = agent_graph.invoke(state)

            # 回放状态事件（图已执行完毕，根据 task_type 告知前端）
            task_type = state.get("task_type", "direct")
            yield sse_event("meta", task_type)

            if task_type == "rag":
                yield sse_event("status", "📚 已从知识库检索到相关内容")
            elif task_type == "tool":
                tool_calls = state.get("tool_calls", [])
                if tool_calls:
                    yield sse_event("tool_call", tool_calls)
                yield sse_event("status", "🔧 已完成工具调用查询")

            # ========== 5. 生成回答（关键流式输出） ==========
            yield sse_event("status", "✍️ 正在生成回答...")

            prompt = state["prompt"]
            llm_history = history[-10:]
            full = ""

            # ★ 使用原生流式 API，直接 SSE 推送（附带工具定义，支持 LLM 直接调工具）
            tool_manager = get_tool_manager()
            tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None

            for chunk in stream_llm(
                "你是一个专业的企业 AI 助手，请用中文回答。你可以使用工具中心的工具（天气查询、数据库查询、HTTP请求、知识库检索等）来获取实时数据。如果用户需要查询天气等实时信息，优先使用相关工具。",
                prompt,
                history=llm_history,
                force_char_level=False,
                tools=tool_schemas,
            ):
                full += chunk
                yield sse_event("chunk", chunk)

            elapsed_ms = int((time.time() - stream_start) * 1000)

            # ★ 记录操作日志（分类：chat.ask_stream）
            OperationLogger.log_chat_question(
                db,
                user_id=user.id,
                question=req.question,
                task_type=task_type,
                is_stream=True,
                conversation_id=conv_id,
                elapsed_ms=elapsed_ms,
                answer=full,
            )

            # ========== 6. 保存 & 完成 ==========
            msg_crud.create_message(db, conv_id, "assistant", full)

            conv = conv_crud.get_conversation(db, conv_id, user.id)
            if conv and (not conv.title or conv.title == "新对话" or len(conv.title) < 2):
                conv.title = req.question[:30]
            db.commit()

            yield sse_event("done", {
                "content": full,
                "conversation_id": conv_id,
            })

        except Exception as e:
            yield sse_event("error", f"系统错误：{str(e)}")
            traceback.print_exc()
        finally:
            db.close()

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


# ========== 诊断端点 ==========
@router.get("/stream-ping")
def stream_ping():
    """
    诊断端点：验证流式基础设施是否正常工作
    每秒输出一个 ping-x，前端应该逐字看到 "ping-0", "ping-1", ...
    如果这里也是全部一次性输出，则问题是 HTTP 流式基础设施层面
    """
    import time
    def gen():
        for i in range(10):
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'ping-{i}'}, ensure_ascii=False)}\n\n"
            time.sleep(0.8)
        yield f"data: {json.dumps({'type': 'done', 'content': 'ok'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
            "Pragma": "no-cache",
        },
    )
