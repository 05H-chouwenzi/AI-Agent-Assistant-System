"""pytest 测试夹具 —— 共享的 HTTP 客户端、认证 token、测试用户"""
import pytest
import pytest_asyncio
import httpx
import uuid
import sys
from pathlib import Path

# 确保 backend 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "http://127.0.0.1:8000"

# ==================== 测试用户（每次运行动态生成，避免冲突） ====================
TEST_USERNAME = f"test_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "Test@123456"


@pytest_asyncio.fixture(scope="session")
async def client():
    """复用的异步 HTTP 客户端（session 级别，一次创建，所有测试复用）"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_token(client):
    """注册测试用户 → 登录 → 返回 Bearer token（整个 session 共享）"""
    # 1. 注册
    resp = await client.post("/api/users/register", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "email": f"{TEST_USERNAME}@test.com",
    })
    assert resp.status_code in (200, 201, 400), f"注册失败: {resp.text}"  # 400 = 可能已存在

    # 2. 登录
    resp = await client.post("/api/users/login", json={
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    data = resp.json()
    assert "token" in data, f"登录响应缺少 token: {data}"
    return f"Bearer {data['token']}"


@pytest_asyncio.fixture(scope="session")
async def auth_headers(auth_token):
    """带认证的请求头"""
    return {"Authorization": auth_token}


@pytest_asyncio.fixture
async def conv_id(client, auth_headers):
    """创建一个测试会话 (function 级别，每个测试独立)"""
    resp = await client.post("/api/conversations/", json={"title": "测试会话"}, headers=auth_headers)
    if resp.status_code == 200:
        return resp.json()["id"]
    return 0
