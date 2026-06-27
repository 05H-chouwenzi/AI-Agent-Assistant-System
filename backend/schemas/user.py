"""
用户相关的 Pydantic 模型 —— 请求/响应校验
"""
from pydantic import BaseModel

# ========== 请求模型 ==========
class UserRegisterRequest(BaseModel):
    """注册请求"""
    username:str
    password:str
    email:str="user@example.com"

class UserLoginRequest(BaseModel):
    """登录请求"""
    username:str
    password:str

# ========== 响应模型 ==========
class UserResponse(BaseModel):
    """注册成功返回"""
    id: int
    username: str
    email: str
    
    class Config:
        from_attributes=True

class LoginResponse(BaseModel):
    """登录成功返回"""
    message:str
    user_id:int
    username:str
    token:str