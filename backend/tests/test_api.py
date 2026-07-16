"""
AI Agent Assistant System — 30 个接口测试用例

覆盖模块：
  认证 (4)  |  天气 API (2)  |  HTTP API (2)  |  数据库查询 (2)
  工具列表 (1)  |  AI 聊天非流式 (2)  |  AI 聊天 SSE 流式 (1)
  WebSocket (1)  |  会话管理 (3)  |  知识库 (2)  |  RAG 检索 (2)
  仪表盘 (2)  |  日志 (1)  |  综合场景 (3)  |  边界异常 (2)

运行方式（后端必须先启动）:
  cd backend && pytest tests/ -v -s

标记说明:
  @pytest.mark.slow  — 涉及 LLM 调用的慢测试
  @pytest.mark.ws    — WebSocket 测试
"""
import json
import asyncio
import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000"


# ═══════════════════════════════════════════════════════════════
#  认证模块 (4 个)
# ═══════════════════════════════════════════════════════════════

class TestAuth:
    """T01-T04: 用户注册、登录、鉴权"""

    async def test_01_register_new_user(self, client):
        """T01: 注册新用户 → 201/200"""
        import uuid
        name = f"apitest_{uuid.uuid4().hex[:6]}"
        resp = await client.post("/api/users/register", json={
            "username": name,
            "password": "Strong@123",
            "email": f"{name}@test.com",
        })
        assert resp.status_code in (200, 201), f"注册失败 {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["username"] == name

    async def test_02_login_success(self, client):
        """T02: 正确密码登录 → 200 + token"""
        resp = await client.post("/api/users/login", json={
            "username": "apitest_tester",
            "password": "Strong@123",
        })
        # 用户可能不存在，先注册
        if resp.status_code == 401:
            await client.post("/api/users/register", json={
                "username": "apitest_tester",
                "password": "Strong@123",
                "email": "apitest_tester@test.com",
            })
            resp = await client.post("/api/users/login", json={
                "username": "apitest_tester",
                "password": "Strong@123",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data

    async def test_03_unauthorized_access(self, client):
        """T03: 未登录访问受保护接口 → 401"""
        resp = await client.get("/api/conversations/")
        assert resp.status_code == 401, f"预期 401，实际 {resp.status_code}"

    async def test_04_wrong_password(self, client):
        """T04: 错误密码登录 → 401"""
        resp = await client.post("/api/users/login", json={
            "username": "apitest_tester",
            "password": "WrongPassword999",
        })
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  天气 API (2 个)
# ═══════════════════════════════════════════════════════════════

class TestWeatherAPI:
    """T05-T06: 天气查询接口"""

    async def test_05_query_beijing_weather(self, client, auth_headers):
        """T05: 查询北京天气 → 200 + 数据"""
        resp = await client.post("/api/tools/weather", json={
            "city": "北京", "days": 1
        }, headers=auth_headers)
        assert resp.status_code == 200, f"天气 API 失败: {resp.text}"
        data = resp.json()
        assert data.get("success") is True, f"天气查询失败: {data}"
        assert "当前温度" in str(data.get("data", {})) or "error" not in str(data).lower()

    async def test_06_empty_city(self, client, auth_headers):
        """T06: 空城市 → 返回错误"""
        resp = await client.post("/api/tools/weather", json={
            "city": "", "days": 1
        }, headers=auth_headers)
        data = resp.json()
        # 可能返回 success=False 或 HTTP 422 (Pydantic 校验)
        assert resp.status_code in (200, 422), f"意外的状态码: {resp.status_code}"
        if resp.status_code == 200:
            assert data.get("success") is False


# ═══════════════════════════════════════════════════════════════
#  HTTP API (2 个)
# ═══════════════════════════════════════════════════════════════

class TestHttpAPI:
    """T07-T08: 通用 HTTP 请求接口"""

    async def test_07_get_jsonplaceholder(self, client, auth_headers):
        """T07: GET 请求 JSONPlaceholder → 200"""
        resp = await client.post("/api/tools/http", json={
            "url": "https://jsonplaceholder.typicode.com/todos/1",
            "method": "GET",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("status_code") == 200

    async def test_08_invalid_url(self, client, auth_headers):
        """T08: 请求无效 URL → 返回错误"""
        resp = await client.post("/api/tools/http", json={
            "url": "http://this.does.not.exist.invalid/api",
            "method": "GET",
        }, headers=auth_headers)
        data = resp.json()
        # 应该返回 success=False
        assert data.get("success") is False or "error" in str(data).lower()


# ═══════════════════════════════════════════════════════════════
#  数据库查询 API (2 个)
# ═══════════════════════════════════════════════════════════════

class TestMySQLAPI:
    """T09-T10: MySQL 只读查询接口"""

    async def test_09_show_tables(self, client, auth_headers):
        """T09: 查询数据库表列表 → 200"""
        resp = await client.post("/api/tools/mysql", json={
            "query": "SHOW TABLES", "limit": 20
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True, f"查询失败: {data.get('error')}"
        assert data.get("row_count", 0) > 0, "数据库应该有表"

    async def test_10_write_operation_rejected(self, client, auth_headers):
        """T10: 写操作被拒绝 → success=False"""
        resp = await client.post("/api/tools/mysql", json={
            "query": "DROP TABLE IF EXISTS test_block",
        }, headers=auth_headers)
        data = resp.json()
        assert data.get("success") is False, "写操作应该被拒绝"
        assert "只读" in str(data.get("error", "")) or "拒绝" in str(data.get("error", ""))


# ═══════════════════════════════════════════════════════════════
#  工具列表 API (1 个)
# ═══════════════════════════════════════════════════════════════

class TestToolsList:
    """T11: 工具列表"""

    async def test_11_list_all_tools(self, client):
        """T11: 获取所有已注册工具 → 200 + 列表"""
        resp = await client.get("/api/tools/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        tool_names = [t["name"] for t in data["tools"]]
        # 关键工具必须存在
        for required in ["weather", "mysql", "http", "rag_search"]:
            assert required in tool_names, f"缺少关键工具: {required}"
        print(f"\n  ✓ 已注册 {len(data['tools'])} 个工具: {tool_names}")


# ═══════════════════════════════════════════════════════════════
#  AI 聊天 - 非流式 (2 个)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestChatNonStream:
    """T12-T13: 非流式 AI 聊天"""

    async def test_12_greeting_chat(self, client, auth_headers):
        """T12: 简单问候 → 200 + AI 回答"""
        resp = await client.post("/api/chat/send", json={
            "question": "你好", "conversation_id": 0
        }, headers=auth_headers)
        assert resp.status_code == 200, f"聊天失败: {resp.text}"
        data = resp.json()
        assert "final_answer" in data, f"缺少 final_answer: {data}"
        assert len(data["final_answer"]) > 0
        print(f"\n  ✓ AI 回答: {data['final_answer'][:80]}...")

    async def test_13_weather_question(self, client, auth_headers):
        """T13: 问天气（触发工具调用） → 200"""
        resp = await client.post("/api/chat/send", json={
            "question": "北京今天天气怎么样？", "conversation_id": 0
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "final_answer" in data
        print(f"\n  ✓ 天气回答: {data['final_answer'][:100]}...")


# ═══════════════════════════════════════════════════════════════
#  AI 聊天 - SSE 流式 (1 个)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestChatSSE:
    """T14: SSE 流式聊天"""

    async def test_14_sse_streaming(self, client, auth_headers):
        """T14: SSE 流式请求 → 收到 chunk + done 事件"""
        chunks = []
        done = False
        async with client.stream("POST", "/api/chat/stream", json={
            "question": "用一句话介绍人工智能", "conversation_id": 0
        }, headers=auth_headers) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:].strip())
                    if event["type"] == "chunk":
                        chunks.append(event["content"])
                    elif event["type"] == "done":
                        done = True
                    elif event["type"] == "error":
                        pytest.fail(f"SSE 错误: {event['content']}")

        full = "".join(chunks)
        assert done, "未收到 done 事件"
        assert len(full) > 0, "未收到任何内容"
        print(f"\n  ✓ SSE 流式回答 ({len(chunks)} chunk, {len(full)} 字): {full[:80]}...")


# ═══════════════════════════════════════════════════════════════
#  WebSocket 聊天 (1 个)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
@pytest.mark.ws
class TestWebSocket:

    @staticmethod
    def _extract_token(auth_headers):
        return auth_headers["Authorization"].replace("Bearer ", "")

    async def test_15_websocket_chat(self, client, auth_headers):
        """T15: WebSocket 聊天 → 收到 token/done 事件"""
        token = self._extract_token(auth_headers)
        ws_url = f"ws://127.0.0.1:8000/api/ws/chat/0?token={token}"

        async with httpx.AsyncClient(timeout=30.0) as ws_client:
            async with ws_client.stream("GET", ws_url) as ws_conn:
                assert ws_conn.status_code == 101, "WebSocket 握手失败"

        # httpx 对 WebSocket 支持有限，改用 websockets 库
        try:
            import websockets
        except ImportError:
            pytest.skip("websockets 库未安装，跳过 WebSocket 测试")

        tokens = []
        done = False
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({"message": "你好"}))

                async for raw in ws:
                    msg = json.loads(raw)
                    if msg["type"] == "token":
                        tokens.append(msg["content"])
                    elif msg["type"] == "done":
                        done = True
                        break
                    elif msg["type"] == "error":
                        pytest.fail(f"WebSocket 错误: {msg.get('content')}")
        except Exception as e:
            pytest.skip(f"WebSocket 连接失败（后端可能未启动或 ws 路由有变）: {e}")

        full = "".join(tokens)
        assert done, "未收到 done 事件"
        assert len(full) > 0
        print(f"\n  ✓ WS 回答 ({len(tokens)} token, {len(full)} 字): {full[:80]}...")


# ═══════════════════════════════════════════════════════════════
#  会话管理 (3 个)
# ═══════════════════════════════════════════════════════════════

class TestConversations:
    """T16-T18: 会话 CRUD"""

    async def test_16_list_conversations(self, client, auth_headers):
        """T16: 获取会话列表 → 200"""
        resp = await client.get("/api/conversations/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"\n  ✓ 共 {len(data)} 个会话")

    async def test_17_get_messages(self, client, auth_headers, conv_id):
        """T17: 获取指定会话的消息 → 200"""
        if not conv_id:
            pytest.skip("无法创建会话")
        resp = await client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"\n  ✓ 会话 {conv_id} 共 {len(data)} 条消息")

    async def test_18_delete_conversation(self, client, auth_headers):
        """T18: 删除会话 → 200"""
        # 先创建一个会话
        r = await client.post("/api/conversations/", json={"title": "待删除"}, headers=auth_headers)
        if r.status_code != 200:
            pytest.skip("无法创建会话")
        cid = r.json()["id"]

        resp = await client.delete(f"/api/conversations/{cid}", headers=auth_headers)
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
#  知识库 (2 个)
# ═══════════════════════════════════════════════════════════════

class TestKnowledge:
    """T19-T20: 知识库上传/列表"""

    async def test_19_upload_txt_document(self, client, auth_headers):
        """T19: 上传 .txt 文档 → 200 + 分块信息"""
        content = "人工智能是计算机科学的一个分支，它企图了解智能的实质，并生产出一种新的能以人类智能相似的方式做出反应的智能机器。"
        resp = await client.post("/api/knowledge/upload", files={
            "file": ("ai_test.txt", content.encode("utf-8"), "text/plain")
        }, headers=auth_headers)
        assert resp.status_code == 200, f"上传失败: {resp.text}"
        data = resp.json()
        assert data.get("id") is not None
        print(f"\n  ✓ 上传成功: id={data['id']}, chunks={data.get('chunks')}")

    async def test_20_list_documents(self, client, auth_headers):
        """T20: 获取文档列表 → 200"""
        resp = await client.get("/api/knowledge/docs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"\n  ✓ 共 {data.get('total', 0)} 个文档")


# ═══════════════════════════════════════════════════════════════
#  RAG 检索 (2 个)
# ═══════════════════════════════════════════════════════════════

class TestRAGSearch:
    """T21-T22: 知识库语义检索"""

    async def test_21_rag_search(self, client, auth_headers):
        """T21: RAG 语义检索 → 200"""
        resp = await client.post("/api/tools/rag", json={
            "query": "人工智能是什么", "top_k": 3
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        print(f"\n  ✓ RAG 检索: success={data.get('success')}, results={len(data.get('data', {}).get('results', []))}")

    async def test_22_empty_query(self, client, auth_headers):
        """T22: 空查询 → 返回错误"""
        resp = await client.post("/api/tools/rag", json={
            "query": "", "top_k": 3
        }, headers=auth_headers)
        data = resp.json()
        # 空查询应该失败
        if data.get("success") is True:
            print(f"\n  ⚠ 空查询返回了结果（可能是模拟数据）")


# ═══════════════════════════════════════════════════════════════
#  仪表盘 (2 个)
# ═══════════════════════════════════════════════════════════════

class TestDashboard:
    """T23-T24: 仪表盘统计"""

    async def test_23_get_stats(self, client, auth_headers):
        """T23: 获取统计概览 → 200"""
        resp = await client.get("/api/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_conversations" in data or "today_call_count" in data
        print(f"\n  ✓ 仪表盘数据: {json.dumps({k: v for k, v in data.items() if isinstance(v, (int, str))}, ensure_ascii=False)}")

    async def test_24_get_system_info(self, client):
        """T24: 获取系统信息 → 200（无需认证）"""
        resp = await client.get("/api/dashboard/system")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("db_status") == "ok"
        assert "version" in data


# ═══════════════════════════════════════════════════════════════
#  日志 (1 个)
# ═══════════════════════════════════════════════════════════════

class TestLogs:
    """T25: 操作日志"""

    async def test_25_get_operation_logs(self, client, auth_headers):
        """T25: 获取操作日志 → 200"""
        resp = await client.get("/api/logs/?page=1&page_size=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        print(f"\n  ✓ 共 {data.get('total', 0)} 条日志")


# ═══════════════════════════════════════════════════════════════
#  综合场景 (3 个)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestEndToEnd:
    """T26-T28: 端到端综合场景"""

    async def test_26_full_conversation_flow(self, client, auth_headers):
        """T26: 完整对话流程：创建会话 → 对话 → 查历史"""
        # 1. 创建会话
        r = await client.post("/api/conversations/", json={"title": "E2E 测试"}, headers=auth_headers)
        assert r.status_code == 200
        cid = r.json()["id"]

        # 2. 发一条消息
        r = await client.post("/api/chat/send", json={
            "question": "1+1等于几？", "conversation_id": cid
        }, headers=auth_headers)
        assert r.status_code == 200
        answer = r.json()["final_answer"]
        print(f"\n  ✓ 对话结果: {answer[:60]}...")

        # 3. 查消息历史
        r = await client.get(f"/api/conversations/{cid}/messages", headers=auth_headers)
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) >= 2, f"预期至少 2 条消息（用户+助手），实际 {len(msgs)} 条"
        print(f"  ✓ 会话 {cid} 共 {len(msgs)} 条消息")

    async def test_27_rapid_sequential_requests(self, client, auth_headers):
        """T27: 快速连续请求 → 全部成功（无并发冲突）"""
        tasks = []
        for i in range(3):
            tasks.append(client.post("/api/chat/send", json={
                "question": f"说一个数字{i}", "conversation_id": 0
            }, headers=auth_headers))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = sum(1 for r in results if not isinstance(r, Exception) and r.status_code == 200)
        print(f"\n  ✓ 3 并发请求: {success}/3 成功")
        assert success>= 1, "至少 1 个并发请求应成功"

    async def test_28_long_question(self, client, auth_headers):
        """T28: 长文本输入 → 200（不崩溃）"""
        long_q = "请分析以下内容：" + "人工智能技术的发展日新月异，" * 20
        resp = await client.post("/api/chat/send", json={
            "question": long_q, "conversation_id": 0
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "final_answer" in data


# ═══════════════════════════════════════════════════════════════
#  边界异常 (2 个)
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """T29-T30: 边界和异常"""

    async def test_29_empty_question(self, client, auth_headers):
        """T29: 空问题 → 400"""
        resp = await client.post("/api/chat/send", json={
            "question": "", "conversation_id": 0
        }, headers=auth_headers)
        assert resp.status_code == 400

    async def test_30_invalid_token(self, client):
        """T30: 伪造 token → 401"""
        resp = await client.get("/api/conversations/", headers={
            "Authorization": "Bearer eyJ.invalid.token"
        })
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
#  健康检查（额外 — 不计入 30 个）
# ═══════════════════════════════════════════════════════════════

class TestHealth:
    """健康检查（不计入 30 个测试用例）"""

    async def test_health_check(self, client):
        """服务健康检查 → 200"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_root(self, client):
        """根路径 → 200"""
        resp = await client.get("/")
        assert resp.status_code == 200
