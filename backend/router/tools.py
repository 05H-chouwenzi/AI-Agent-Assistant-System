"""
工具 API 路由 —— 提供工具的直接 REST API 调用接口
"""
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Optional
from sqlalchemy.orm import Session

from tools.base_tool import ToolResult
from tools.tool_manager import get_tool_manager
from logs.logger import logger
from database.session import get_db
from models.user import User
from utils.auth import get_current_user
from logs.operation_logger import OperationLogger, Actions
from utils.client_ip import get_client_ip

router = APIRouter(prefix="/api/tools", tags=["工具中心"])


class WeatherRequest(BaseModel):
    """天气查询请求"""
    city: str
    days: Optional[int] = 1


class WeatherResponse(BaseModel):
    """天气查询响应"""
    success: bool
    data: dict = {}
    error: str = ""
    execution_time_ms: float = 0


class DatabaseQueryRequest(BaseModel):
    """数据库查询请求"""
    query: str
    limit: Optional[int] = 50


class DatabaseQueryResponse(BaseModel):
    """数据库查询响应"""
    success: bool
    columns: list = []
    rows: list = []
    row_count: int = 0
    query: str = ""
    error: str = ""
    execution_time_ms: float = 0


class HttpRequest(BaseModel):
    """HTTP 请求"""
    url: str
    method: str = "GET"
    headers: dict = {}
    body: str = ""


class HttpResponse(BaseModel):
    """HTTP 响应"""
    success: bool
    status_code: int = 0
    method: str = ""
    url: str = ""
    response: Any = None
    error: str = ""
    execution_time_ms: float = 0


class RAGSearchRequest(BaseModel):
    """知识库检索请求"""
    query: str
    top_k: Optional[int] = 5


class RAGSearchResponse(BaseModel):
    """知识库检索响应"""
    success: bool
    data: dict = {}
    error: str = ""
    execution_time_ms: float = 0


@router.post("/rag", response_model=RAGSearchResponse)
def search_knowledge(
    req: RAGSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    搜索企业内部知识库

    根据查询词从向量库中检索最相关的文档片段，返回相关内容及来源。
    """
    manager = get_tool_manager()
    tool = manager.get("rag_search")

    if tool is None:
        raise HTTPException(status_code=500, detail="知识库检索工具未注册")

    start = time.time()
    result: ToolResult = tool.execute(query=req.query.strip(), top_k=req.top_k or 5)
    elapsed = (time.time() - start) * 1000

    if result.success:
        logger.info(f"知识库检索成功: '{req.query[:30]}' ({elapsed:.0f}ms)")

        # ★ 记录操作日志
        OperationLogger.log_rag_search(
            db,
            user_id=current_user.id,
            query=req.query,
            docs_count=len(result.data.get("results", [])) if isinstance(result.data, dict) else 1,
            success=True,
            source="api",
            elapsed_ms=int(elapsed),
        )

        return RAGSearchResponse(
            success=True,
            data=result.data if isinstance(result.data, dict) else {"result": result.data},
            execution_time_ms=round(elapsed, 2),
        )
    else:
        logger.warning(f"知识库检索失败: {result.error}")

        OperationLogger.log_rag_search(
            db,
            user_id=current_user.id,
            query=req.query,
            docs_count=0,
            success=False,
            source="api",
            elapsed_ms=int(elapsed),
        )

        return RAGSearchResponse(
            success=False,
            error=result.error or "检索失败",
            execution_time_ms=round(elapsed, 2),
        )


@router.post("/weather", response_model=WeatherResponse)
def query_weather(
    req: WeatherRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询指定城市的实时天气信息

    使用 wttr.in 免费 API，支持中文/英文城市名
    """
    manager = get_tool_manager()
    tool = manager.get("weather")

    if tool is None:
        raise HTTPException(status_code=500, detail="天气工具未注册")

    start = time.time()
    result: ToolResult = tool.execute(city=req.city.strip(), days=req.days or 1)
    elapsed = (time.time() - start) * 1000

    if result.success:
        logger.info(f"天气查询成功: {req.city} ({elapsed:.0f}ms)")

        # ★ 记录操作日志
        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_WEATHER,
            tool_name="weather",
            params={"city": req.city, "days": req.days},
            result_summary=f"{req.city} 天气查询成功",
            success=True,
            elapsed_ms=int(elapsed),
        )

        return WeatherResponse(
            success=True,
            data=result.data if isinstance(result.data, dict) else {"result": result.data},
            execution_time_ms=round(elapsed, 2),
        )
    else:
        logger.warning(f"天气查询失败: {req.city} - {result.error}")

        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_WEATHER,
            tool_name="weather",
            params={"city": req.city, "days": req.days},
            result_summary=f"失败: {result.error}",
            success=False,
            elapsed_ms=int(elapsed),
        )

        return WeatherResponse(
            success=False,
            error=result.error or "查询失败",
            execution_time_ms=round(elapsed, 2),
        )


@router.post("/mysql", response_model=DatabaseQueryResponse)
def query_database(
    req: DatabaseQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    执行 MySQL 只读查询（SELECT / SHOW / DESCRIBE / EXPLAIN）

    参数:
        - query: SQL 查询语句
        - limit: 返回行数上限（默认 50，最大 200）
    """
    manager = get_tool_manager()
    tool = manager.get("mysql")

    if tool is None:
        raise HTTPException(status_code=500, detail="数据库查询工具未注册")

    start = time.time()
    result: ToolResult = tool.execute(query=req.query.strip(), limit=req.limit or 50)
    elapsed = (time.time() - start) * 1000

    if result.success:
        data = result.data if isinstance(result.data, dict) else {}
        raw_rows = data.get("结果", [])
        query_text = data.get("查询", req.query)

        # 提取列名并按顺序构建 rows
        columns = []
        rows = []
        if raw_rows and isinstance(raw_rows, list):
            # 从第一条结果提取列名
            first = raw_rows[0]
            if isinstance(first, dict):
                columns = list(first.keys())
                rows = [[row.get(col, "") for col in columns] for row in raw_rows]

        logger.info(f"数据库查询成功: {len(rows)} 行 ({elapsed:.0f}ms)")

        # ★ 记录操作日志
        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_MYSQL,
            tool_name="mysql",
            params={"query": query_text[:200], "limit": req.limit},
            result_summary=f"查询 {len(rows)} 行",
            success=True,
            elapsed_ms=int(elapsed),
        )

        return DatabaseQueryResponse(
            success=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            query=query_text,
            execution_time_ms=round(elapsed, 2),
        )
    else:
        logger.warning(f"数据库查询失败: {result.error}")

        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_MYSQL,
            tool_name="mysql",
            params={"query": req.query[:200], "limit": req.limit},
            result_summary=f"失败: {result.error}",
            success=False,
            elapsed_ms=int(elapsed),
        )

        return DatabaseQueryResponse(
            success=False,
            error=result.error or "查询失败",
            execution_time_ms=round(elapsed, 2),
        )


@router.get("/list")
def list_tools():
    """列出所有已注册的工具"""
    manager = get_tool_manager()
    tools = []
    for t in manager.list_tools():
        tools.append({
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        })
    return {"tools": tools}


@router.post("/http", response_model=HttpResponse)
def send_http_request(
    req: HttpRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送 HTTP 请求到指定 URL

    支持 GET / POST / PUT / DELETE 方法，
    可自定义请求头和请求体
    """
    manager = get_tool_manager()
    tool = manager.get("http")

    if tool is None:
        raise HTTPException(status_code=500, detail="HTTP 请求工具未注册")

    method = req.method.upper().strip()
    if method not in ("GET", "POST", "PUT", "DELETE"):
        raise HTTPException(status_code=400, detail=f"不支持的 HTTP 方法: {method}")

    start = time.time()
    result: ToolResult = tool.execute(
        url=req.url.strip(),
        method=method,
        headers=req.headers or {},
        body=req.body,
    )
    elapsed = (time.time() - start) * 1000

    if result.success:
        data = result.data if isinstance(result.data, dict) else {}
        logger.info(f"HTTP 请求成功: {method} {req.url} ({elapsed:.0f}ms) 状态码={data.get('状态码', '?')}")

        # ★ 记录操作日志
        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_HTTP,
            tool_name="http",
            params={"method": method, "url": req.url, "headers": req.headers},
            result_summary=f"{method} {req.url} -> {data.get('状态码', '?')}",
            success=True,
            elapsed_ms=int(elapsed),
        )

        return HttpResponse(
            success=True,
            status_code=data.get("状态码", 0),
            method=data.get("方法", method),
            url=data.get("URL", req.url),
            response=data.get("响应"),
            execution_time_ms=round(elapsed, 2),
        )
    else:
        logger.warning(f"HTTP 请求失败: {method} {req.url} - {result.error}")

        OperationLogger.log_tool_call(
            db,
            user_id=current_user.id,
            action=Actions.TOOL_HTTP,
            tool_name="http",
            params={"method": method, "url": req.url},
            result_summary=f"失败: {result.error}",
            success=False,
            elapsed_ms=int(elapsed),
        )

        return HttpResponse(
            success=False,
            error=result.error or "请求失败",
            execution_time_ms=round(elapsed, 2),
        )
