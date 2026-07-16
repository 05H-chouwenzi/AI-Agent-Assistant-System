"""
JWT 鉴权 —— token 签发 & 验证

所有敏感配置从 config.settings 导入，避免硬编码密钥。
"""
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from config.settings import JWT_SECRET

# ========== 配置 ==========
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# ========== 安全方案 ==========
bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict) -> str:
    """生成JWT token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """解析 JWT token，返回 payload，失败返回 None"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user_id(token: str) -> Optional[int]:
    """从 token 中提取用户 ID"""
    payload = decode_access_token(token)
    if not payload:
        return None
    raw = payload.get("sub")
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    if isinstance(raw, int):
        return raw
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析token获取当前用户(依赖注入)"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="无效的token")
    raw = payload.get("sub")
    if isinstance(raw, str) and raw.isdigit():
        raw = int(raw)
    if raw is None:
        raise HTTPException(status_code=401, detail="无效的token")
    user_id = int(raw)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_tenant_access(current_user: User = Depends(get_current_user)) -> User:
    """验证用户属于某个租户"""
    if not current_user.tenant_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="用户未关联任何租户")
    return current_user


def require_permission(role: str = "member"):
    """权限检查依赖"""
    def checker(current_user: User = Depends(get_current_user)):
        ALLOWED = {"admin": ["admin"], "member": ["admin", "member"]}
        if current_user.role not in ALLOWED.get(role, ["member"]):
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker
