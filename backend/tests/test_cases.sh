#!/bin/bash
# =============================================================================
# AI Agent Assistant System — 30 个测试用例（curl 格式，可直接复制运行）
# =============================================================================
# 使用前先设置 TOKEN（先注册+登录获取）
#   或用 ./test_cases.sh auto   → 自动注册登录
# =============================================================================

BASE="http://localhost:8000"

if [ "$1" = "auto" ]; then
  echo "=== 自动注册 & 登录 ==="
  REG=$(curl -s -X POST "$BASE/api/users/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser_'$(date +%s)'","password":"test123","email":"test@test.com"}')
  echo "注册: $REG"

  LOGIN=$(curl -s -X POST "$BASE/api/users/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser_'$(date +%s)'","password":"test123"}' 2>/dev/null)
  TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token','ERROR'))" 2>/dev/null)

  if [ "$TOKEN" = "ERROR" ] || [ -z "$TOKEN" ]; then
    echo ">>> 自动登录失败，请手动设置 TOKEN: export TOKEN=你的token"
    echo "响应: $LOGIN"
    exit 1
  fi
  echo "Token: ${TOKEN:0:30}..."
else
  if [ -z "$TOKEN" ]; then
    echo ">>> 请先设置 TOKEN: export TOKEN=你的jwt_token"
    echo ">>> 或者运行: ./test_cases.sh auto"
    exit 1
  fi
fi

echo ""
echo "============================================"
echo "  开始执行 30 个测试用例"
echo "============================================"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ① 通用对话 / AI 助手（6 例）
# ═══════════════════════════════════════════════════════════════════════════

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ① 通用对话 / AI 助手"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. 简单问候 → FastRouter 旁路，零 LLM
echo ""
echo "[1/30] 简单问候 → FastRouter 旁路"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"你好"}'
echo ""

# 2. 日期时间 → FastRouter 旁路
echo ""
echo "[2/30] 日期时间 → FastRouter"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"今天几号"}'
echo ""

# 3. 数学计算 → FastRouter 旁路
echo ""
echo "[3/30] 数学计算 → FastRouter"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"计算 1234 * 5678"}'
echo ""

# 4. 常识问答 → General Agent
echo ""
echo "[4/30] 常识问答 → General Agent (LLM)"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"什么是机器学习？用中文简单解释"}'
echo ""

# 5. 翻译 → General Agent
echo ""
echo "[5/30] 翻译 → General Agent"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"把 hello world 翻译成中文"}'
echo ""

# 6. 流式输出 → SSE
echo ""
echo "[6/30] 流式输出 → SSE"
curl -s -N -X POST "$BASE/api/chat/stream" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"用50字介绍深度学习"}'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ② 天气 API（4 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ② 天气 API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 7. 直接调天气工具
echo ""
echo "[7/30] 查询北京天气"
curl -s -X POST "$BASE/api/tools/weather" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"city":"Beijing"}'
echo ""

# 8. 通过聊天触发天气工具（AI 自动路由到 weather tool）
echo ""
echo "[8/30] AI 对话触发天气工具 → Research Agent"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"北京今天天气怎么样？"}'
echo ""

# 9. 天气 + 预报天数
echo ""
echo "[9/30] 查询上海 3 天预报"
curl -s -X POST "$BASE/api/tools/weather" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"city":"Shanghai","days":3}'
echo ""

# 10. 天气参数缺失
echo ""
echo "[10/30] 天气 → 空城市（异常）"
curl -s -X POST "$BASE/api/tools/weather" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"city":""}'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ③ HTTP API（3 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ③ HTTP API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 11. 正常 GET 请求
echo ""
echo "[11/30] HTTP GET JSONPlaceholder"
curl -s -X POST "$BASE/api/tools/http" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"https://jsonplaceholder.typicode.com/posts/1","method":"GET"}'
echo ""

# 12. POST 请求
echo ""
echo "[12/30] HTTP POST 请求"
curl -s -X POST "$BASE/api/tools/http" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"https://jsonplaceholder.typicode.com/posts","method":"POST","body":"{\"title\":\"test\",\"body\":\"hello\",\"userId\":1}","headers":"{\"Content-Type\":\"application/json\"}"}'
echo ""

# 13. 无效 URL
echo ""
echo "[13/30] HTTP → 无效 URL（异常）"
curl -s -X POST "$BASE/api/tools/http" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"url":"https://this-domain-does-not-exist-xyz123.com","method":"GET"}'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ④ 数据库查询 API（3 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ④ 数据库查询 API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 14. 查看表结构
echo ""
echo "[14/30] 数据库 → 查看所有表"
curl -s -X POST "$BASE/api/tools/mysql" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"SHOW TABLES"}'
echo ""

# 15. 查询数据
echo ""
echo "[15/30] 数据库 → 查询用户表"
curl -s -X POST "$BASE/api/tools/mysql" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"SELECT id, username, created_at FROM users LIMIT 5"}'
echo ""

# 16. 写操作被拒绝
echo ""
echo "[16/30] 数据库 → 尝试 DROP（应被拒绝）"
curl -s -X POST "$BASE/api/tools/mysql" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"DROP TABLE users"}'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ⑤ 工具管理（2 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⑤ 工具管理"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 17. 工具列表
echo ""
echo "[17/30] 列出所有可用工具"
curl -s -X GET "$BASE/api/tools/list" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# 18. 健康检查
echo ""
echo "[18/30] 健康检查 → /api/health"
curl -s -X GET "$BASE/api/health"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ⑥ 会话管理（3 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⑥ 会话管理"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 19. 获取会话列表
echo ""
echo "[19/30] 会话列表"
curl -s -X GET "$BASE/api/conversations/" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# 20. 创建新会话并发消息
echo ""
echo "[20/30] 创建新会话 + 发消息"
CONV=$(curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"你好，请记住我"}')
echo "$CONV"
# 提取 conversation_id
CID=$(echo "$CONV" | python3 -c "import sys,json; print(json.load(sys.stdin).get('conversation_id','0'))" 2>/dev/null)
echo ">>> 会话 ID: $CID"

# 21. 获取该会话历史消息
echo ""
echo "[21/30] 获取会话消息历史"
if [ -n "$CID" ] && [ "$CID" != "0" ]; then
  curl -s -X GET "$BASE/api/conversations/$CID/messages" \
    -H "Authorization: Bearer $TOKEN"
else
  echo ">>> 跳过：未获取到会话 ID"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ⑦ 知识库 + RAG 检索（4 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⑦ 知识库 + RAG 检索"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 22. RAG 语义检索
echo ""
echo "[22/30] RAG 检索 → 人工智能"
curl -s -X POST "$BASE/api/tools/rag" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"什么是人工智能"}'
echo ""

# 23. RAG 空查询
echo ""
echo "[23/30] RAG → 空查询（异常）"
curl -s -X POST "$BASE/api/tools/rag" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":""}'
echo ""

# 24. 知识库文档列表
echo ""
echo "[24/30] 知识库 → 文档列表"
curl -s -X GET "$BASE/api/knowledge/docs" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# 25. 通过聊天触发 RAG
echo ""
echo "[25/30] AI 对话触发 RAG 知识库检索"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":"根据知识库，什么是机器学习？"}'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ⑧ 仪表盘 & 日志（2 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⑧ 仪表盘 & 日志"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 26. 仪表盘统计
echo ""
echo "[26/30] 仪表盘 → 统计概览"
curl -s -X GET "$BASE/api/dashboard/stats" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# 27. 系统状态
echo ""
echo "[27/30] 仪表盘 → 系统信息"
curl -s -X GET "$BASE/api/dashboard/system" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# 28. 操作日志
echo ""
echo "[28/30] 操作日志列表"
curl -s -X GET "$BASE/api/logs/" \
  -H "Authorization: Bearer $TOKEN"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ⑨ 认证 & 异常边界（2 例）
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ⑨ 认证 & 异常边界"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 29. 无认证访问 → 401
echo ""
echo "[29/30] 未认证访问 → 应返回 401"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Content-Type: application/json" \
  -d '{"question":"你好"}'
echo ""

# 30. 空问题
echo ""
echo "[30/30] 空问题 → 应返回 400"
curl -s -X POST "$BASE/api/chat/send" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"question":""}'
echo ""

echo ""
echo "============================================"
echo "  30 个测试用例执行完毕！"
echo "============================================"
