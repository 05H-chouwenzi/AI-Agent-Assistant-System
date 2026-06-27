"""
JWT 鉴权 —— token 签发 & 验证
"""
from datetime import datetime,timedelta,timezone
from jose import jwt,JWTError
from fastapi import Depends,HTTPException
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User

# ========== 配置（后续移到配置文件） ==========
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# ========== 安全方案 ==========
bearer_scheme = HTTPBearer(auto_error=False)

def create_access_token(data:dict)->str:
    """生成JWT token"""
    to_encode=data.copy()
    expire=datetime.now(timezone.utc)+timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp":expire})
    return jwt.encode(to_encode,SECRET_KEY,algorithm=ALGORITHM)

def get_current_user(
    credentials:HTTPAuthorizationCredentials=Depends(bearer_scheme),
    db:Session=Depends(get_db),
)->User:
    """解析token获取当前用户(依赖注入)"""
    if credentials is None:
        raise HTTPException(status_code=401,detail="未提供认证信息")
    try:
        payload=jwt.decode(
            credentials.credentials,SECRET_KEY,algorithms=[ALGORITHM]
        )
        user_id:int=payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401,detail="无效的token")
    except JWTError:
        raise HTTPException(status_code=401,detail="用户不存在")
    user=db.query(User).filter(User.id==user_id).first()
    if user is None:
        raise HTTPException(status_code=401,detail="用户不存在")
    return user