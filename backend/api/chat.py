"""
聊天接口 —— 接收用户消息，调用 Agent Workflow，返回结果
"""
import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.session import get_db
from agent.workflow import build_workflow
from logs.logger import log_agent_decision, log_final_answer

router = APIRouter(prefix="/api/chat", tags=["聊天"])

agent_app = build_workflow()


class ChatRequest(BaseModel):
    """聊天请求"""
    question: str


class ChatResponse(BaseModel):
    """聊天响应"""
    question: str
    task_type: str
    final_answer: str


@router.post("/send", response_model=ChatResponse)
def chat_send(req: ChatRequest, db: Session = Depends(get_db)):
    """用户发送消息 → Agent 处理 → 返回结果"""
    start = time.time()
    initial_state = {"question": req.question}

    result = agent_app.invoke(initial_state)
    elapsed_ms = (time.time() - start) * 1000

    # === 记录日志 ===
    log_agent_decision(db, req.question, result.get("task_type", "unknown"))
    log_final_answer(db, req.question, result.get("final_answer", ""), elapsed_ms)

    return ChatResponse(
        question=result["question"],
        task_type=result.get("task_type", "unknown"),
        final_answer=result.get("final_answer", "抱歉，我无法回答这个问题"),
    )