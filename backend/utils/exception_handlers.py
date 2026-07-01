"""
全局异常处理器 —— 统一错误响应
"""
from fastapi import HTTPException 
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError,SQLAlchemyError

from utils.response import error_response

async def http_exception_handler(request:Request,exc:HTTPException):
    """HTTP异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(message=exc.detail,code=exc.status_code),
    )

async def integrity_error_handler(request:Request,exc:IntegrityError):
    """数据库唯一约束冲突"""
    return JSONResponse(
        status_code=400,
        content=error_response(message="数据冲突,请检查输入",code=400)
    )

async def sqlalchemy_error_handler(request:Request,exc:SQLAlchemyError):
    """数据库其他错误"""

    return JSONResponse(
        status_code=500,
        content=error_response(message="服务器内部错误",code=500),
    )

async def general_exception_handler(request:Request,exc:Exception):
   """未捕获的异常"""
   import traceback
   traceback.print_exc()
   return JSONResponse(
       status_code=500,
       content=error_response(message=f"服务器内部错误: {str(exc)}",code=500),
   )