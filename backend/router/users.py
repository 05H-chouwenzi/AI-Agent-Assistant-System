"""
用户路由 —— 注册 & 登录
"""
from utils.security import hash_password, verify_password
from utils.auth import create_access_token, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.session import get_db
from models.user import User
from schemas.user import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    LoginResponse,
    ProfileUpdateRequest,
    PasswordChangeRequest,
)
router = APIRouter(prefix="/api/users", tags=["用户"])


@router.post("/register", response_model=UserResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 自动生成唯一邮箱：如果未传邮箱或邮箱为默认值/已被占用，则用用户名+时间戳生成
    email = req.email
    if email == "user@example.com" or db.query(User).filter(User.email == email).first():
        import time
        email = f"{req.username}_{int(time.time())}@example.com"
        # 极低概率冲突，再检查一次
        while db.query(User).filter(User.email == email).first():
            import random
            email = f"{req.username}_{int(time.time())}_{random.randint(100,999)}@example.com"

    if len(req.password) > 72:
        raise HTTPException(status_code=400, detail="密码不能超过72位")

    user = User(
        username=req.username,
        email=email,
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

    token = create_access_token(data={"sub": str(user.id)})
    return LoginResponse(
        message="登陆成功",
        user_id=user.id,
        username=user.username,
        token=token,
    )


@router.get("/profile", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    req: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改个人资料"""
    if req.email is not None:
        # 检查邮箱是否被其他用户使用
        existing = db.query(User).filter(User.email == req.email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        current_user.email = req.email
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/password")
def change_password(
    req: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改密码"""
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(req.new_password) > 72:
        raise HTTPException(status_code=400, detail="密码不能超过72位")
    current_user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}
