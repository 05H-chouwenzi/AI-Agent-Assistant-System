"""
用户路由 —— 注册 & 登录（含操作日志）
"""
from utils.security import hash_password, verify_password
from utils.auth import create_access_token, get_current_user
from fastapi import APIRouter, Depends, HTTPException, Request
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
from logs.operation_logger import OperationLogger, Actions
from utils.client_ip import get_client_ip
from crud import user as user_crud

router = APIRouter(prefix="/api/users", tags=["用户"])


@router.post("/register", response_model=UserResponse)
def register(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    existing = user_crud.get_user_by_username(db, req.username)
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 自动生成唯一邮箱：如果未传邮箱或邮箱为默认值/已被占用，则用用户名+时间戳生成
    email = req.email
    if email == "user@example.com" or user_crud.get_user_by_email(db, email):
        import time
        email = f"{req.username}_{int(time.time())}@example.com"
        # 极低概率冲突，再检查一次
        while user_crud.get_user_by_email(db, email):
            import random
            email = f"{req.username}_{int(time.time())}_{random.randint(100,999)}@example.com"

    if len(req.password) > 72:
        raise HTTPException(status_code=400, detail="密码不能超过72位")

    user = user_crud.create_user(db, req.username, email, hash_password(req.password))

    # 自动创建租户
    from models.tenant import Tenant
    tenant = Tenant(name=f"{req.username} 的工作空间")
    db.add(tenant)
    db.flush()
    user.tenant_id = tenant.id
    user.role = "admin"
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=LoginResponse)
def login(req: UserLoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    user = user_crud.get_user_by_username(db, req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(data={"sub": str(user.id)})

    # ★ 记录登录操作（没有 request 依赖，无法取 IP）
    OperationLogger.log_user_event(
        db,
        action=Actions.USER_LOGIN,
        user_id=user.id,
        username=user.username,
        detail={"login_ip": None},
        success=True,
    )

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
    old_email = current_user.email
    if req.email is not None:
        # 检查邮箱是否被其他用户使用
        existing = user_crud.get_user_by_email(db, req.email)
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="邮箱已被注册")
        user_crud.update_user_email(db, current_user, req.email)

    # ★ 记录资料修改
    OperationLogger.log_user_event(
        db,
        action=Actions.USER_PROFILE_UPDATE,
        user_id=current_user.id,
        username=current_user.username,
        detail={"old_email": old_email, "new_email": current_user.email},
        success=True,
    )

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
    user_crud.update_user_password(db, current_user, hash_password(req.new_password))

    # ★ 记录修改密码
    OperationLogger.log_user_event(
        db,
        action=Actions.USER_PASSWORD_CHANGE,
        user_id=current_user.id,
        username=current_user.username,
        success=True,
    )

    return {"message": "密码修改成功"}
