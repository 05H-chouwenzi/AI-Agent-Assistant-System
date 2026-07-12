"""
聊天接口 —— 接收用户消息，调用 Agent 节点，返回结果

新的处理流程：
                 用户
                   │
           FastRouter（规则）
           │              │
        命中             未命中
          │               │
        Tool         Planner → ToolRouter → Tool
          │               │
    ┌─────┴─────┐    LLM 总结
    │           │         │
  is_final   需 LLM     返回
    │           │
 Formatter   Prompt Builder
    │           │
   返回        LLM
                │
               返回
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from agent.state.agent_state import AgentState
from agent.workflow import agent_graph
from agent.nodes.fast_router import FastRouter
from agent.nodes.formatter import Formatter
from agent.nodes.llm_node import build_prompt
from services.llm_service import call_llm
from logs.operation_logger import OperationLogger, Actions
from tools.tool_manager import get_tool_manager
from crud import conversation as conv_crud
from crud import message as msg_crud

router = APIRouter(prefix="/api/chat", tags=["聊天"])

# 全局单例 —— 模块加载时初始化，避免每次请求重复创建
_fast_router = FastRouter()
_formatter = Formatter()

# 默认系统提示词
SYSTEM_PROMPT = (
    "你是一个专业的企业 AI 助手，请用中文回答。"
    "你可以使用工具中心的工具（天气查询、数据库查询、计算器、HTTP请求、知识库检索等）来获取实时数据。"
    "如果用户需要查询天气等实时信息，优先使用相关工具。"
)


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str
    conversation_id: int = 0


class ChatResponse(BaseModel):
    """聊天响应"""
    question: str
    task_type: str
    final_answer: str


def _load_history(db: Session, conv_id: int, user_id: int) -> list:
    """加载会话历史消息"""
    history = []
    if conv_id and conv_id > 0:
        conv = conv_crud.get_conversation(db, conv_id, user_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        past_messages = msg_crud.get_conversation_messages(db, conv_id)
        for m in past_messages:
            history.append({"role": m.role, "content": m.content})
    return history


def _save_messages(db: Session, conv_id: int, question: str, answer: str, user_id: int):
    """保存消息到数据库"""
    if conv_id and conv_id > 0:
        conv = conv_crud.get_conversation(db, conv_id, user_id)
        if conv:
            msg_crud.create_message(db, conv_id, "user", question)
            msg_crud.create_message(db, conv_id, "assistant", answer)
            if not conv.title or conv.title == "新对话" or len(conv.title) < 2:
                conv.title = question[:30]
            db.commit()


@router.post("/send", response_model=ChatResponse)
def chat_send(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户发送消息 → 处理 → 返回结果

    流程：
      1. FastRouter 规则匹配（零 LLM 调用）
         - 命中且 is_final: Tool → Formatter → 返回（~0.2~1s）
         - 命中且 !is_final: Tool → LLM → 返回（~2~4s）
      2. 未命中: Planner → ToolRouter(规则优先) → Tool → LLM → 返回（~3~8s）
    """
    # 加载历史消息
    history = _load_history(db, req.conversation_id, current_user.id)
    start = time.time()
    elapsed_ms = 0

    try:
        # ========== 1. FastRouter 快速匹配 ==========
        match = _fast_router.route(req.question)

        if match is not None:
            # 命中 FastRouter → 直接执行工具
            tool_manager = get_tool_manager()
            tool_result = tool_manager.execute(match.tool_name, **match.tool_args)

            if match.is_final and tool_result.success:
                # ✅ 快速路径：工具结果就是最终答案 → Formatter 直接返回
                # 跳过 Planner、ToolRouter(LLM)、LLM 回答 的全流程
                answer = _formatter.format(match.tool_name, tool_result)
                task_type = f"fast:{match.rule_name}"
                elapsed_ms = int((time.time() - start) * 1000)
                logger.info(
                    f"FastRouter 快速路径: [{match.rule_name}] "
                    f"耗时 {elapsed_ms}ms"
                )

                result = {
                    "question": req.question,
                    "task_type": task_type,
                    "final_answer": answer,
                }

            elif tool_result.success:
                # ⚠️ 需要 LLM 进一步处理（如分析、总结）
                # 构建带工具结果的提示词，跳过图直接调 LLM
                tool_state: AgentState = {
                    "question": req.question,
                    "history": history[-10:],
                    "user_id": current_user.id,
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
                answer = call_llm(SYSTEM_PROMPT, prompt, history=history[-10:])
                elapsed_ms = int((time.time() - start) * 1000)

                result = {
                    "question": req.question,
                    "task_type": f"fast:{match.rule_name}",
                    "final_answer": answer,
                }

            else:
                # 工具执行失败 → 友好降级
                # 为天气工具提供更快的降级响应（避免调 LLM）
                if match.tool_name == "weather":
                    answer = f"❌ 暂时无法获取 {match.tool_args.get('city', '')} 的天气信息，请稍后再试。"
                else:
                    fallback_state: AgentState = {
                        "question": req.question,
                        "history": history[-10:],
                        "user_id": current_user.id,
                        "task_type": "direct",
                    }
                    prompt = build_prompt(fallback_state)
                    answer = call_llm(SYSTEM_PROMPT, prompt, history=history[-10:])
                elapsed_ms = int((time.time() - start) * 1000)

                result = {
                    "question": req.question,
                    "task_type": f"fast:{match.rule_name}_fallback",
                    "final_answer": answer,
                }

        else:
            # ========== 2. FastRouter 未命中 → 走完整 Agent 流程 ==========
            state: AgentState = {
                "question": req.question,
                "history": history[-10:],
                "user_id": current_user.id,
            }

            # 2a. LangGraph Workflow：planner → (rag/tool) → prompt_builder
            state = agent_graph.invoke(state)

            # 2b. LLM 调用
            tool_manager = get_tool_manager()
            tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None

            answer = call_llm(
                SYSTEM_PROMPT,
                state["prompt"],
                history=history[-10:],
                tools=tool_schemas,
            )

            elapsed_ms = int((time.time() - start) * 1000)

            result = {
                "question": req.question,
                "task_type": state.get("task_type", "direct"),
                "final_answer": answer,
            }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"chat_send 异常: {str(e)}", exc_info=True)
        result = {
            "question": req.question,
            "task_type": "error",
            "final_answer": f"系统错误：{str(e)}",
        }

    # === 记录操作日志 ===
    OperationLogger.log_chat_question(
        db,
        user_id=current_user.id,
        question=req.question,
        task_type=result.get("task_type", "unknown"),
        is_stream=False,
        conversation_id=req.conversation_id or None,
        elapsed_ms=elapsed_ms,
        answer=result.get("final_answer", ""),
    )

    # 保存消息到数据库
    if req.conversation_id and req.conversation_id > 0:
        _save_messages(
            db, req.conversation_id, req.question,
            result.get("final_answer", ""), current_user.id,
        )

    return ChatResponse(
        question=result["question"],
        task_type=result.get("task_type", "unknown"),
        final_answer=result.get("final_answer", "抱歉，我无法回答这个问题"),
    )


@router.post("/send-with-trace")
def chat_send_with_trace(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    用户发送消息 → Agent 处理 → 返回结果（不含追踪）
    （该端点沿用 /send 的实现，如需调试信息请查看服务端日志）
    """
    # 复用同一个处理逻辑
    from fastapi.responses import JSONResponse

    start = time.time()
    history = _load_history(db, req.conversation_id, current_user.id)

    try:
        # FastRouter 快速匹配
        match = _fast_router.route(req.question)

        if match is not None:
            tool_manager = get_tool_manager()
            tool_result = tool_manager.execute(match.tool_name, **match.tool_args)

            if match.is_final and tool_result.success:
                answer = _formatter.format(match.tool_name, tool_result)
                task_type = f"fast:{match.rule_name}"
            elif tool_result.success:
                tool_state: AgentState = {
                    "question": req.question,
                    "history": history[-10:],
                    "user_id": current_user.id,
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
                answer = call_llm(SYSTEM_PROMPT, prompt, history=history[-10:])
                task_type = f"fast:{match.rule_name}"
            else:
                # 天气工具快速降级，不调 LLM
                if match.tool_name == "weather":
                    answer = f"❌ 暂时无法获取 {match.tool_args.get('city', '')} 的天气信息，请稍后再试。"
                else:
                    fallback_state: AgentState = {
                        "question": req.question,
                        "history": history[-10:],
                        "user_id": current_user.id,
                        "task_type": "direct",
                    }
                    prompt = build_prompt(fallback_state)
                    answer = call_llm(SYSTEM_PROMPT, prompt, history=history[-10:])
                task_type = f"fast:{match.rule_name}_fallback"

            elapsed_ms = int((time.time() - start) * 1000)

            result = {
                "question": req.question,
                "task_type": task_type,
                "final_answer": answer,
            }
        else:
            state: AgentState = {
                "question": req.question,
                "history": history[-10:],
                "user_id": current_user.id,
            }
            state = agent_graph.invoke(state)

            tool_manager = get_tool_manager()
            tool_schemas = tool_manager.get_function_schemas() if not tool_manager.is_empty() else None
            answer = call_llm(
                SYSTEM_PROMPT, state["prompt"],
                history=history[-10:], tools=tool_schemas,
            )
            elapsed_ms = int((time.time() - start) * 1000)

            result = {
                "question": req.question,
                "task_type": state.get("task_type", "direct"),
                "final_answer": answer,
            }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        result = {
            "question": req.question,
            "task_type": "error",
            "final_answer": f"系统错误：{str(e)}",
        }

    # 记录操作日志
    OperationLogger.log_chat_question(
        db,
        user_id=current_user.id,
        question=req.question,
        task_type=result.get("task_type", "unknown"),
        is_stream=False,
        conversation_id=req.conversation_id or None,
        elapsed_ms=elapsed_ms,
        answer=result.get("final_answer", ""),
    )

    # 保存消息
    if req.conversation_id and req.conversation_id > 0:
        _save_messages(
            db, req.conversation_id, req.question,
            result.get("final_answer", ""), current_user.id,
        )

    return {
        "response": ChatResponse(
            question=result["question"],
            task_type=result.get("task_type", "unknown"),
            final_answer=result.get("final_answer", ""),
        ),
    }