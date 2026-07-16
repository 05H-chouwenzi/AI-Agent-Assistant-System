"""
MySQL Tool —— 数据库查询工具（只读，安全查询）
"""
import json
import time
import re
import asyncio
from tools.base_tool import BaseTool, ToolResult, _json_safe
from config.settings import DATABASE_URL
from database.session import engine as _db_engine
from sqlalchemy import text as sa_text


class MySQLTool(BaseTool):
    """
    数据库查询工具

    默认只允许 SELECT / SHOW / DESCRIBE / EXPLAIN 等只读操作，
    防止 LLM 误操作修改或删除数据。
    """

    # 允许的只读 SQL 关键词
    _READONLY_KEYWORDS = {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN"}

    def __init__(self, database_url: str | None = None):
        """
        database_url: SQLAlchemy 连接字符串，如 'mysql+pymysql://user:pass@host:port/db'
        如果为 None，则使用 config.settings 中的 DATABASE_URL
        """
        self._database_url = database_url or DATABASE_URL

    @property
    def name(self) -> str:
        return "mysql"

    @property
    def description(self) -> str:
        return (
            "查询企业内部 MySQL 数据库。只支持只读操作（SELECT/SHOW/DESCRIBE/EXPLAIN）。"
            "可用于查询业务数据、报表、用户信息等。"
            "执行前会做安全检查，禁止 INSERT/UPDATE/DELETE/DROP 等写操作。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL 查询语句（仅允许 SELECT/SHOW/DESCRIBE/EXPLAIN）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回行数上限，默认 50，最大 200",
                    "default": 50
                }
            },
            "required": ["query"]
        }

    def _is_readonly(self, sql: str) -> bool:
        """检查 SQL 是否是只读操作"""
        stripped = sql.strip().upper()
        # 去掉开头注释
        stripped = re.sub(r'^/\*.*?\*/', '', stripped, flags=re.DOTALL).strip()
        stripped = re.sub(r'^--.*$', '', stripped, flags=re.MULTILINE).strip()

        first_word = stripped.split()[0] if stripped else ""
        return first_word in self._READONLY_KEYWORDS

    def _parse_db_url(self) -> dict:
        """解析 SQLAlchemy 连接字符串"""
        # mysql+pymysql://user:pass@host:port/db
        pattern = r'^mysql\+pymysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)$'
        match = re.match(pattern, self._database_url)
        if not match:
            raise ValueError(f"无法解析数据库连接字符串: {self._database_url}")
        return {
            "user": match.group(1),
            "password": match.group(2),
            "host": match.group(3),
            "port": int(match.group(4)),
            "database": match.group(5),
        }

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        limit = min(kwargs.get("limit", 50), 200)

        if not query:
            return ToolResult(success=False, error="缺少 SQL 查询参数", tool_name=self.name)

        if not self._is_readonly(query):
            return ToolResult(
                success=False,
                error=f"只允许只读操作 ({', '.join(sorted(self._READONLY_KEYWORDS))})，"
                      f"当前查询被拒绝。如需执行写操作，请联系管理员。",
                tool_name=self.name,
            )

        # 自动加 LIMIT（如果没有的话）
        if "LIMIT" not in query.upper():
            query = f"{query.rstrip(';')} LIMIT {limit}"

        start = time.time()
        try:
            # 使用 SQLAlchemy 连接池（复用已有连接，避免每次 TCP 握手）
            with _db_engine.connect() as conn:
                result = conn.execute(sa_text(query))
                rows = [dict(row._mapping) for row in result]

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data={
                    "查询": query,
                    "行数": len(rows),
                    "结果": _json_safe(rows),
                },
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

        except ImportError:
            return ToolResult(success=False, error="pymysql 未安装", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, error=f"数据库错误: {str(e)}", tool_name=self.name)

    async def aexecute(self, **kwargs) -> ToolResult:
        """异步版本：将同步数据库操作放入线程池，不阻塞事件循环"""
        query = kwargs.get("query", "").strip()
        limit = min(kwargs.get("limit", 50), 200)

        if not query:
            return ToolResult(success=False, error="缺少 SQL 查询参数", tool_name=self.name)

        if not self._is_readonly(query):
            return ToolResult(
                success=False,
                error=f"只允许只读操作 ({', '.join(sorted(self._READONLY_KEYWORDS))})，"
                      f"当前查询被拒绝。如需执行写操作，请联系管理员。",
                tool_name=self.name,
            )

        if "LIMIT" not in query.upper():
            query = f"{query.rstrip(';')} LIMIT {limit}"

        start = time.time()
        try:
            # 使用连接池 + 线程池，数据库操作不阻塞事件循环
            import pymysql
            db_info = self._parse_db_url()

            def _do_query():
                conn = pymysql.connect(
                    host=db_info["host"],
                    port=db_info["port"],
                    user=db_info["user"],
                    password=db_info["password"],
                    database=db_info["database"],
                    charset="utf8mb4",
                    connect_timeout=10,
                    read_timeout=15,
                )
                try:
                    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                        cursor.execute(query)
                        return cursor.fetchall()
                finally:
                    conn.close()

            rows = await asyncio.to_thread(_do_query)

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data={
                    "查询": query,
                    "行数": len(rows),
                    "结果": _json_safe(rows),
                },
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

        except ImportError:
            return ToolResult(success=False, error="pymysql 未安装", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, error=f"数据库错误: {str(e)}", tool_name=self.name)
