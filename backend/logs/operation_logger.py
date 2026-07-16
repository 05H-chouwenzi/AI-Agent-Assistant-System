"""
操作日志 —— 记录用户每一次操作到 MySQL，按动作分类

使用方式:
    from logs.operation_logger import OperationLogger

    # 在 FastAPI 端点中
    OperationLogger.log_tool_call(db, user_id=current_user.id,
        action="tool.weather", tool_name="weather", city="北京", ...)

模块分类:
    agent  — 通用 Agent 操作（用户/知识库/RAG/仪表盘/系统）
    chat   — 聊天相关操作
    tool   — 工具调用操作
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from models.system_log import SystemLog

logger = logging.getLogger("agent")


# ── 动作分类常量 ──────────────────────────────────────────────
class Actions:
    """操作分类 —— 所有 action 常量"""
    # 用户
    USER_LOGIN = "user.login"
    USER_REGISTER = "user.register"
    USER_PROFILE_UPDATE = "user.profile_update"
    USER_PASSWORD_CHANGE = "user.password_change"

    # 聊天
    CHAT_ASK = "chat.ask"              # 非流式提问
    CHAT_ASK_STREAM = "chat.ask_stream"  # 流式提问

    # RAG 检索
    RAG_SEARCH = "rag.search"          # 通过工具路由检索
    RAG_SEARCH_DIRECT = "rag.search_direct"  # 通过 REST API 检索

    # 工具
    TOOL_WEATHER = "tool.weather"      # 天气查询
    TOOL_MYSQL = "tool.mysql"          # 数据库查询
    TOOL_HTTP = "tool.http"            # HTTP 请求

    # 知识库
    KNOWLEDGE_UPLOAD = "knowledge.upload"
    KNOWLEDGE_DELETE = "knowledge.delete"
    KNOWLEDGE_LIST = "knowledge.list"

    # 会话
    CONVERSATION_CREATE = "conversation.create"
    CONVERSATION_DELETE = "conversation.delete"
    CONVERSATION_VIEW = "conversation.view"
    CONVERSATION_LIST = "conversation.list"

    # 仪表盘
    DASHBOARD_STATS = "dashboard.stats"
    DASHBOARD_TRENDS = "dashboard.trends"
    DASHBOARD_SYSTEM = "dashboard.system"


# ── 简化模块映射：全部归入 agent / chat / tool ──────────────────
ACTION_MODULE_MAP = {
    # agent 范畴
    Actions.USER_LOGIN: "agent",
    Actions.USER_REGISTER: "agent",
    Actions.USER_PROFILE_UPDATE: "agent",
    Actions.USER_PASSWORD_CHANGE: "agent",
    Actions.RAG_SEARCH: "agent",
    Actions.RAG_SEARCH_DIRECT: "agent",
    Actions.KNOWLEDGE_UPLOAD: "agent",
    Actions.KNOWLEDGE_DELETE: "agent",
    Actions.KNOWLEDGE_LIST: "agent",
    Actions.DASHBOARD_STATS: "agent",
    Actions.DASHBOARD_TRENDS: "agent",
    Actions.DASHBOARD_SYSTEM: "agent",

    # chat 范畴
    Actions.CHAT_ASK: "chat",
    Actions.CHAT_ASK_STREAM: "chat",
    Actions.CONVERSATION_CREATE: "chat",
    Actions.CONVERSATION_DELETE: "chat",
    Actions.CONVERSATION_VIEW: "chat",
    Actions.CONVERSATION_LIST: "chat",

    # tool 范畴
    Actions.TOOL_WEATHER: "tool",
    Actions.TOOL_MYSQL: "tool",
    Actions.TOOL_HTTP: "tool",
}


class OperationLogger:
    """统一的操作日志写入器"""

    @staticmethod
    def _resolve_module(action: str) -> str:
        """从 action 推断 module，兜底返回 system"""
        return ACTION_MODULE_MAP.get(action, "system")

    @staticmethod
    def write(
        db: Session,
        *,
        action: str,
        message: str,
        log_level: str = "info",
        user_id: Optional[int] = None,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
    ) -> SystemLog:
        """写入一条操作日志（核心方法）"""
        module = OperationLogger._resolve_module(action)
        log = SystemLog(
            log_level=log_level,
            module=module,
            action=action,
            message=message,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
            user_id=user_id,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            execution_time_ms=execution_time_ms,
        )
        db.add(log)
        db.commit()
        logger.debug(f"[操作日志] {action} | {message}")
        return log

    # ── 专用快捷方法 ─────────────────────────────────────

    @staticmethod
    def log_user_event(
        db: Session,
        *,
        action: str,
        user_id: Optional[int],
        username: str,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
    ):
        """用户相关操作（登录/注册/资料修改）"""
        level = "info" if success else "warning"
        action_labels = {
            Actions.USER_LOGIN: "用户登录",
            Actions.USER_REGISTER: "用户注册",
            Actions.USER_PROFILE_UPDATE: "修改资料",
            Actions.USER_PASSWORD_CHANGE: "修改密码",
        }
        label = action_labels.get(action, action)
        return OperationLogger.write(
            db,
            action=action,
            log_level=level,
            message=f"{label}: {username}",
            user_id=user_id,
            detail=detail,
            ip_address=ip_address,
            resource_type="user",
            resource_id=str(user_id) if user_id else None,
        )

    @staticmethod
    def log_chat_question(
        db: Session,
        *,
        user_id: int,
        question: str,
        task_type: str,
        is_stream: bool = False,
        ip_address: Optional[str] = None,
        conversation_id: Optional[int] = None,
        elapsed_ms: Optional[int] = None,
        answer: Optional[str] = None,
    ):
        """记录用户向 AI 提问"""
        action = Actions.CHAT_ASK_STREAM if is_stream else Actions.CHAT_ASK
        return OperationLogger.write(
            db,
            action=action,
            message=f"AI提问: {question[:80]} -> 类型={task_type}",
            log_level="info",
            user_id=user_id,
            detail={
                "question": question,
                "task_type": task_type,
                "is_stream": is_stream,
                "answer_preview": answer[:200] if answer else None,
            },
            ip_address=ip_address,
            resource_type="conversation",
            resource_id=str(conversation_id) if conversation_id else None,
            execution_time_ms=elapsed_ms,
        )

    @staticmethod
    def log_tool_call(
        db: Session,
        *,
        user_id: int,
        action: str,
        tool_name: str,
        params: Optional[dict] = None,
        result_summary: str = "",
        success: bool = True,
        ip_address: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
    ):
        """记录工具调用（天气/数据库/HTTP）"""
        level = "info" if success else "warning"
        action_labels = {
            Actions.TOOL_WEATHER: "天气查询",
            Actions.TOOL_MYSQL: "数据库查询",
            Actions.TOOL_HTTP: "HTTP请求",
        }
        label = action_labels.get(action, tool_name)
        return OperationLogger.write(
            db,
            action=action,
            log_level=level,
            message=f"{label}: {result_summary[:100] if result_summary else '完成'}",
            user_id=user_id,
            detail={
                "tool": tool_name,
                "params": params,
                "success": success,
                "result": result_summary[:500] if result_summary else None,
            },
            ip_address=ip_address,
            resource_type="tool",
            resource_id=tool_name,
            execution_time_ms=elapsed_ms,
        )

    @staticmethod
    def log_rag_search(
        db: Session,
        *,
        user_id: int,
        query: str,
        docs_count: int,
        success: bool = True,
        source: str = "agent",  # "agent" | "api"
        ip_address: Optional[str] = None,
        elapsed_ms: Optional[int] = None,
    ):
        """记录 RAG 知识库检索"""
        action = Actions.RAG_SEARCH_DIRECT if source == "api" else Actions.RAG_SEARCH
        level = "info" if success else "warning"
        return OperationLogger.write(
            db,
            action=action,
            log_level=level,
            message=f"知识库检索: {query[:60]} -> {docs_count} 条结果",
            user_id=user_id,
            detail={
                "query": query,
                "docs_count": docs_count,
                "source": source,
                "success": success,
            },
            ip_address=ip_address,
            resource_type="rag",
            execution_time_ms=elapsed_ms,
        )

    @staticmethod
    def log_knowledge_event(
        db: Session,
        *,
        action: str,
        user_id: int,
        doc_title: str,
        detail: Optional[dict] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
    ):
        """记录知识库文档操作（上传/删除）"""
        level = "info" if success else "warning"
        action_labels = {
            Actions.KNOWLEDGE_UPLOAD: "上传文档",
            Actions.KNOWLEDGE_DELETE: "删除文档",
        }
        label = action_labels.get(action, "知识库操作")
        return OperationLogger.write(
            db,
            action=action,
            log_level=level,
            message=f"{label}: {doc_title}",
            user_id=user_id,
            detail=detail,
            ip_address=ip_address,
            resource_type="knowledge_doc",
            resource_id=doc_title,
        )

    @staticmethod
    def log_conversation_event(
        db: Session,
        *,
        action: str,
        user_id: int,
        conv_title: str,
        conv_id: Optional[int] = None,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ):
        """记录会话操作（创建/删除/查看）"""
        action_labels = {
            Actions.CONVERSATION_CREATE: "创建会话",
            Actions.CONVERSATION_DELETE: "删除会话",
            Actions.CONVERSATION_VIEW: "查看消息",
            Actions.CONVERSATION_LIST: "获取会话列表",
        }
        label = action_labels.get(action, "会话操作")
        return OperationLogger.write(
            db,
            action=action,
            message=f"{label}: {conv_title}",
            log_level="info",
            user_id=user_id,
            detail=detail,
            ip_address=ip_address,
            resource_type="conversation",
            resource_id=str(conv_id) if conv_id else None,
        )

# ── 异步后台写入（火抛，不阻塞请求路径）──────────────────────

import asyncio

async def async_log_chat_question(
    *,
    user_id: int,
    question: str,
    task_type: str,
    is_stream: bool = False,
    conversation_id: int | None = None,
    elapsed_ms: int | None = None,
    answer: str | None = None,
):
    """异步后台写入聊天操作日志，不阻塞请求路径"""
    def _sync_write():
        db = SessionLocal()
        try:
            OperationLogger.log_chat_question(
                db, user_id=user_id, question=question,
                task_type=task_type, is_stream=is_stream,
                conversation_id=conversation_id,
                elapsed_ms=elapsed_ms, answer=answer,
            )
        except Exception as e:
            logger.warning(f"异步日志写入失败（可忽略）: {e}")
        finally:
            db.close()
    await asyncio.to_thread(_sync_write)


async def async_log_conversation_event(
    *,
    action: str,
    user_id: int,
    conv_title: str,
    conv_id: int | None = None,
):
    """异步后台写入会话操作日志"""
    def _sync_write():
        db = SessionLocal()
        try:
            OperationLogger.log_conversation_event(
                db, action=action, user_id=user_id,
                conv_title=conv_title, conv_id=conv_id,
            )
        except Exception as e:
            logger.warning(f"异步会话日志写入失败（可忽略）: {e}")
        finally:
            db.close()
    await asyncio.to_thread(_sync_write)

async def async_log_knowledge_event(
    *,
    action: str,
    user_id: int,
    doc_title: str,
    detail: dict | None = None,
    success: bool = True,
):
    def _sync_write():
        db = SessionLocal()
        try:
            OperationLogger.log_knowledge_event(
                db, action=action, user_id=user_id,
                doc_title=doc_title, detail=detail, success=success,
            )
        except Exception as e:
            logger.warning(f"异步知识库日志写入失败（可忽略）: {e}")
        finally:
            db.close()
    await asyncio.to_thread(_sync_write)
