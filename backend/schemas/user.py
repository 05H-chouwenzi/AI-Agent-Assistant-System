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


class ProfileUpdateRequest(BaseModel):
    """修改个人资料"""
    email: str | None = None


class PasswordChangeRequest(BaseModel):
    """修改密码"""
    old_password: str
    new_password: str