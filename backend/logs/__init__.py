"""
日志服务 —— 记录 Agent 全链路日志到 MySQL
"""
import json
import time
from sqlalchemy.orm import Session
from models.system_log import SystemLog


def write_log(
    db: Session,
    log_level: str,
    module: str,
    message: str,
    detail: dict = None,
):
    """写入一条日志"""
    log = SystemLog(
        log_level=log_level,
        module=module,
        message=message,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
    )
    db.add(log)
    db.commit()


def log_agent_decision(db: Session, question: str, task_type: str):
    """记录 Planner 决策"""
    write_log(
        db,
        log_level="info",
        module="agent",
        message=f"问题分类: {task_type}",
        detail={"question": question, "task_type": task_type},
    )


def log_tool_call(db: Session, tool_name: str, result: str):
    """记录工具调用"""
    write_log(
        db,
        log_level="info",
        module="tool",
        message=f"调用工具: {tool_name}",
        detail={"tool": tool_name, "result": result},
    )


def log_rag_retrieval(db: Session, question: str, docs_count: int):
    """记录知识库检索"""
    write_log(
        db,
        log_level="info",
        module="rag",
        message=f"检索完成: {docs_count} 条结果",
        detail={"question": question, "docs_count": docs_count},
    )


def log_final_answer(db: Session, question: str, answer: str, elapsed_ms: float):
    """记录最终回答"""
    write_log(
        db,
        log_level="info",
        module="agent",
        message="生成回答完成",
        detail={
            "question": question,
            "answer": answer,
            "elapsed_ms": elapsed_ms,
        },
    )