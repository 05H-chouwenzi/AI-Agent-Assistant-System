"""
HTTP Tool —— 通用 HTTP 请求工具（支持 GET / POST / PUT / DELETE）
"""
import json
import time
import urllib.request
import urllib.error
from tools.base_tool import BaseTool, ToolResult


class HttpTool(BaseTool):

    @property
    def name(self) -> str:
        return "http"

    @property
    def description(self) -> str:
        return (
            "发送 HTTP 请求到指定 URL，获取或提交数据。"
            "支持 GET、POST、PUT、DELETE 方法。"
            "适用于调用外部 API、查询公开数据等场景。"
            "返回响应状态码和响应体（JSON 或纯文本）。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "请求的完整 URL，如 'https://api.example.com/data'"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP 请求方法，默认 GET",
                    "default": "GET"
                },
                "headers": {
                    "type": "object",
                    "description": "自定义请求头，JSON 对象格式",
                    "additionalProperties": {"type": "string"}
                },
                "body": {
                    "type": "string",
                    "description": "请求体（JSON 字符串），仅 POST/PUT 时使用"
                }
            },
            "required": ["url"]
        }

    def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "").strip()
        method = kwargs.get("method", "GET").upper().strip()
        headers = kwargs.get("headers") or {}
        body = kwargs.get("body")

        if not url:
            return ToolResult(success=False, error="缺少 URL 参数", tool_name=self.name)

        if method not in ("GET", "POST", "PUT", "DELETE"):
            return ToolResult(success=False, error=f"不支持的 HTTP 方法: {method}", tool_name=self.name)

        start = time.time()
        try:
            # 默认请求头
            req_headers = {
                "User-Agent": "AI-Agent-Assistant/1.0",
                "Accept": "application/json, text/plain, */*",
            }
            req_headers.update(headers)

            data = None
            if body and method in ("POST", "PUT"):
                data = body.encode("utf-8")
                req_headers.setdefault("Content-Type", "application/json")

            req = urllib.request.Request(
                url, data=data, headers=req_headers, method=method
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                status_code = resp.status

            # 尝试解析 JSON
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw[:2000]  # 截断长文本

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data={
                    "状态码": status_code,
                    "方法": method,
                    "URL": url,
                    "响应": parsed,
                },
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

        except urllib.error.HTTPError as e:
            return ToolResult(
                success=False,
                error=f"HTTP {e.code}: {e.reason}",
                tool_name=self.name,
            )
        except urllib.error.URLError as e:
            return ToolResult(
                success=False,
                error=f"网络连接失败: {str(e.reason)}",
                tool_name=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"请求失败: {str(e)}",
                tool_name=self.name,
            )
