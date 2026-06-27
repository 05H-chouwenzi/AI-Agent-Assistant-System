"""
用户路由 —— 注册 & 登录
"""
from utils.security import hash_password, verify_password
from utils.auth import create_access_token
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    LoginResponse,
)
router = APIRouter(prefix="/api/users", tags=["用户"])


@router.post("/register", response_model=UserResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    existing_email = db.query(User).filter(User.email == req.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    if len(req.password) > 72:
        raise HTTPException(status_code=400, detail="密码不能超过72位")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=LoginResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(data={"sub": user.id})
    return LoginResponse(
        message="登陆成功",
        user_id=user.id,
        username=user.username,
        token=token,
    )
