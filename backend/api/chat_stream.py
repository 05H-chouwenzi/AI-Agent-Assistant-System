"""
聊天流式接口 —— SSE 逐字推送 + 完整多轮记忆（支持工具调用）

核心改进：
1. 每个处理阶段前 yield status 事件，让用户看到 AI "正在思考"
2. 支持 direct / rag / tool 三种任务类型的实时状态反馈
3. 参考「AI黑马项目」的 chain.stream 模式，先发状态再发数据
"""
import json
import traceback
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database.session import SessionLocal
from models.conversation import Conversation
from models.message import Message
from models.user import User
from utils.auth import get_current_user
from fastapi import HTTPException
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from services.llm_service import stream_llm

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

    SSE 事件类型:
      - status: 中间状态（思考、检索、调用工具、生成）
      - meta:   任务类型信息
      - tool_call: 工具调用信息（tool_name 等），前端可渲染为可点击跳转标签
      - chunk:  LLM 逐字输出
      - done:   完成事件
      - error:  错误事件
    """
    def event_stream():
        """同步生成器：在 thread pool 中运行，每个 yield 立即推送"""
        db = SessionLocal()
        try:
            # ========== 1. 会话初始化 ==========
            conv_id = req.conversation_id
            if not conv_id or conv_id == 0:
                conv = Conversation(title=req.question[:30], user_id=user.id)
                db.add(conv)
                db.commit()
                db.refresh(conv)
                conv_id = conv.id

            # 加载历史消息
            history = []
            if conv_id and conv_id > 0:
                conv = (
                    db.query(Conversation)
                    .filter(Conversation.id == conv_id, Conversation.user_id == user.id)
                    .first()
                )
                if not conv:
                    yield sse_event("error", "对话不存在")
                    return

                past_messages = (
                    db.query(Message)
                    .filter(Message.conversation_id == conv_id)
                    .order_by(Message.created_at.asc())
                    .all()
                )
                for m in past_messages:
                    history.append({"role": m.role, "content": m.content})

            # 用户消息入库
            user_msg = Message(conversation_id=conv_id, role="user", content=req.question)
            db.add(user_msg)
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

            # ★ 使用原生流式 API，直接 SSE 推送
            for chunk in stream_llm(
                "你是一个专业的企业 AI 助手，请用中文回答。如用户问题涉及企业内部知识或需实时数据，结合参考信息回答。",
                prompt,
                history=llm_history,
                force_char_level=False,
            ):
                full += chunk
                yield sse_event("chunk", chunk)

            # ========== 6. 保存 & 完成 ==========
            ai_msg = Message(conversation_id=conv_id, role="assistant", content=full)
            db.add(ai_msg)

            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if conv and (not conv.title or conv.title == "新对话" or len(conv.title) < 2):
                conv.title = req.question[:30]
            db.commit()

            yield sse_event("done", {
                "content": full,
                "message_id": ai_msg.id,
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
