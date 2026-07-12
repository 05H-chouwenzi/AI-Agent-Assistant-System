"""
聊天流式接口 —— SSE 逐字推送 + 完整多轮记忆（集成 FastRouter）

新的处理流程：
    用户
      │
  FastRouter（规则）
   │              │
 命中             未命中
   │                │
  Tool         Planner → ToolRouter → Tool → LLM 流式
   │
  ┌──┴──┐
  │     │
is_final  需 LLM
  │        │
 Formatter  Prompt Builder
  │        │
 逐字推送   LLM 流式
  │        │
 done     done
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
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from agent.nodes.fast_router import FastRouter
from agent.nodes.formatter import Formatter
from agent.nodes.llm_node import build_prompt
from services.llm_service import stream_llm
from logs.operation_logger import OperationLogger, Actions
from crud import conversation as conv_crud
from crud import message as msg_crud
from tools.tool_manager import get_tool_manager

router = APIRouter(prefix="/api/chat", tags=["聊天"])

# 全局单例
_fast_router = FastRouter()
_formatter = Formatter()

# 默认系统提示词
SYSTEM_PROMPT = (
    "你是一个专业的企业 AI 助手，请用中文回答。"
    "你可以使用工具中心的工具（天气查询、数据库查询、计算器、HTTP请求、知识库检索等）来获取实时数据。"
    "如果用户需要查询天气等实时信息，优先使用相关工具。"
)


class ChatStreamRequest(BaseModel):
    question: str
    conversation_id: int = 0


def sse_event(event_type: str, content, ensure_ascii=False) -> str:
    """快速构造 SSE 事件 JSON 字符串"""
    return f"data: {json.dumps({'type': event_type, 'content': content}, ensure_ascii=ensure_ascii)}\n\n"


def _save_to_db(db: Session, conv_id: int, question: str, answer: str, user_id: int):
    """保存消息并更新会话标题"""
    if conv_id:
        conv = conv_crud.get_conversation(db, conv_id, user_id)
        if conv:
            if not conv.title or conv.title == "新对话" or len(conv.title) < 2:
                conv.title = question[:30]
            db.commit()


def _build_state_with_prompt_for_history(state, history):
    """构建带历史信息的完整 state"""
    state["history"] = history[-10:]
    return state


@router.post("/stream")
async def chat_stream(req: ChatStreamRequest, user: User = Depends(get_current_user)):
    """
    流式：FastRouter → (Tool → Formatter/LLM) or (Planner → Tool → LLM) → SSE

    三种路径：
      1. FastRouter 命中 + is_final       : Tool → Formatter → 逐字推送（最快）
      2. FastRouter 命中 + !is_final      : Tool → LLM 流式    （中等）
      3. FastRouter 未命中                 : 原有 Agent 流程     （标准）
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

            # ========== 2. FastRouter 快速匹配 ==========
            question = req.question
            match = _fast_router.route(question)

            if match is not None:
                # ───────────────── FastRouter 命中 ─────────────────
                task_type = f"fast:{match.rule_name}"

                # 2a. 执行工具
                yield sse_event("meta", task_type)
                yield sse_event("status", f"⚡ 正在调用 {match.tool_name}...")

                tool_manager = get_tool_manager()
                tool_result = tool_manager.execute(match.tool_name, **match.tool_args)

                if match.is_final and tool_result.success:
                    # ✅ 快速路径: Formatter 直接出结果，按句子推送
                    yield sse_event("status", "📋 正在格式化结果...")
                    answer = _formatter.format(match.tool_name, tool_result)

                    # 按标点断句推送，一段话一段话地出（比逐字快多了）
                    i = 0
                    while i < len(answer):
                        # 找下一个句子结束标点
                        sent_end = len(answer)
                        for sep in "。！？\n":
                            pos = answer.find(sep, i)
                            if pos != -1 and pos + 1 < sent_end:
                                sent_end = pos + 1
                        chunk = answer[i:sent_end]
                        if chunk.strip():
                            yield sse_event("chunk", chunk)
                        i = sent_end

                    elapsed_ms = int((time.time() - stream_start) * 1000)

                elif tool_result.success:
                    # ⚠️ 需要 LLM 总结：构建 prompt → 流式 LLM
                    yield sse_event("status", "🔧 工具调用完成，正在生成回答...")

                    tool_state: AgentState = {
                        "question": question,
                        "history": history[-10:],
                        "user_id": user.id,
                        "task_type": "tool",
                        "tool_result": tool_result.to_message(),
                        "tool_results": [tool_result.to_dict()],
                        "tool_calls": [{
                            "tool_name": match.tool_name,
                            "arguments": match.tool_args,
                            "result": tool_result.to_dict(),
                            "success": tool_result.success,
                            "error": tool_result.error,
                            "execution_time_ms": tool_result.execution_time_ms,
                        }],
                    }
                    prompt = build_prompt(tool_state)

                    full = ""
                    for chunk in stream_llm(
                        SYSTEM_PROMPT, prompt,
                        history=history[-10:],
                        force_char_level=False,
                    ):
                        full += chunk
                        yield sse_event("chunk", chunk)

                    answer = full
                    elapsed_ms = int((time.time() - stream_start) * 1000)

                else:
                    # 工具失败 → LLM 兜底
                    yield sse_event("status", "工具调用异常，正在尝试直接回答...")

                    # 天气工具直接返回友好提示，不调 LLM
                    if match.tool_name == "weather":
                        answer = f"❌ 暂时无法获取 {match.tool_args.get('city', '')} 的天气信息，请稍后再试。"
                        elapsed_ms = int((time.time() - stream_start) * 1000)
                        for chunk in [answer]:
                            yield sse_event("chunk", chunk)
                    else:
                        fallback_state: AgentState = {
                            "question": question,
                            "history": history[-10:],
                            "user_id": user.id,
                            "task_type": "direct",
                        }
                        prompt = build_prompt(fallback_state)

                        full = ""
                        for chunk in stream_llm(
                            SYSTEM_PROMPT, prompt,
                            history=history[-10:],
                            force_char_level=False,
                        ):
                            full += chunk
                            yield sse_event("chunk", chunk)

                        answer = full
                        elapsed_ms = int((time.time() - stream_start) * 1000)

            else:
                # ───────────────── FastRouter 未命中 ─────────────────

                # 2b. 初始化 Agent 状态
                state: AgentState = {
                    "question": question,
                    "history": history[-10:],
                    "user_id": user.id,
                }

                # 2c. LangGraph Workflow
                state = agent_graph.invoke(state)

                # 回放状态事件
                task_type = state.get("task_type", "direct")
                yield sse_event("meta", task_type)

                if task_type == "rag":
                    yield sse_event("status", "📚 已从知识库检索到相关内容")
                elif task_type == "tool":
                    tool_calls = state.get("tool_calls", [])
                    if tool_calls:
                        yield sse_event("tool_call", tool_calls)
                    yield sse_event("status", "🔧 已完成工具调用查询")

                # 2d. LLM 流式生成
                yield sse_event("status", "✍️ 正在生成回答...")

                prompt = state["prompt"]
                llm_history = history[-10:]
                full = ""

                tool_manager = get_tool_manager()
                tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None

                for chunk in stream_llm(
                    SYSTEM_PROMPT,
                    prompt,
                    history=llm_history,
                    force_char_level=False,
                    tools=tool_schemas,
                ):
                    full += chunk
                    yield sse_event("chunk", chunk)

                answer = full
                elapsed_ms = int((time.time() - stream_start) * 1000)

            # ========== 3. 记录 & 保存 ==========
            # 记录操作日志
            OperationLogger.log_chat_question(
                db,
                user_id=user.id,
                question=question,
                task_type=task_type,
                is_stream=True,
                conversation_id=conv_id,
                elapsed_ms=elapsed_ms,
                answer=answer,
            )

            # 保存消息
            msg_crud.create_message(db, conv_id, "assistant", answer)
            _save_to_db(db, conv_id, question, answer, user.id)

            yield sse_event("done", {
                "content": answer,
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