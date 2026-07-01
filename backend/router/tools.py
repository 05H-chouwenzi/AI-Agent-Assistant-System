"""
工具 API 路由 —— 提供工具的直接 REST API 调用接口
"""
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from tools.base_tool import ToolResult
from tools.tool_manager import get_tool_manager
from logs.logger import logger

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


@router.post("/weather", response_model=WeatherResponse)
def query_weather(req: WeatherRequest):
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
        return WeatherResponse(
            success=True,
            data=result.data if isinstance(result.data, dict) else {"result": result.data},
            execution_time_ms=round(elapsed, 2),
        )
    else:
        logger.warning(f"天气查询失败: {req.city} - {result.error}")
        return WeatherResponse(
            success=False,
            error=result.error or "查询失败",
            execution_time_ms=round(elapsed, 2),
        )


@router.post("/mysql", response_model=DatabaseQueryResponse)
def query_database(req: DatabaseQueryRequest):
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
def send_http_request(req: HttpRequest):
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
        return HttpResponse(
            success=False,
            error=result.error or "请求失败",
            execution_time_ms=round(elapsed, 2),
        )
