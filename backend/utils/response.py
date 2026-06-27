"""
统一响应格式
"""
from typing import Any,Optional

def success_response(
    data:Any=None,
    message:str="ok",
    code:int=200
)->dict:
    """成功响应"""
    return {
        "code":code,
        "message":message,
        "data":data,
    }

def error_response(
    message:str="error",
    code:int=400,
    data:Any=None
)->dict:
    """错误响应"""
    return {
        "code":code,
        "message":message,
        "data":data,
    }