"""
统一响应格式
"""
from typing import Any


def error_response(
    message: str = "error",
    code: int = 400,
    data: Any = None
) -> dict:
    """错误响应"""
    return {
        "code": code,
        "message": message,
        "data": data,
    }