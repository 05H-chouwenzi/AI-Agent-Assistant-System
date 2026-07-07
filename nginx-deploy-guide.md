# =============================================================================

# 部署配置详细说明

# — Nginx 反向代理 + 前端/后端

# =============================================================================

# =========================================

# 快速开始（5 分钟）

# =========================================

# 1. 下载安装 Nginx（Windows）

# https://nginx.org/en/download.html → nginx/Windows-x.y.z.zip

# 解压到 C:\nginx 或任意无中文路径

# 2. 复制配置文件

# 将本项目中的 nginx.conf 复制到 C:\nginx\conf\nginx.conf

# （建议先备份原有的 nginx.conf）

# 3. 修改路径（根据实际位置）

# nginx.conf 中的 root 路径：

# root E:/Workspace/AI_Agent_Assistant_System/frontend/dist;

# uploads alias 路径：

# alias E:/Workspace/AI_Agent_Assistant_System/backend/uploads/;

# → 改为你电脑上的实际绝对路径（正斜杠，不要反斜杠）

# 4. 构建前端

# cd frontend

# npm install # 如果没有装过依赖

# npm run build # 输出到 frontend/dist

# 5. 启动后端

# cd backend

# python main.py # FastAPI 会在 :8004 启动

# 6. 启动 nginx

# C:\nginx> nginx.exe

# 或: nginx.exe -t -c conf\nginx.conf # 先检查配置

# 浏览器访问 http://localhost 即可

# =========================================

# 开发模式（使用 Vite 热更新）

# =========================================

# 如果要用 Vite 热更新（不构建），修改 nginx.conf：

# 1. 注释掉 "root" + "location /" 块

# 2. 取消注释 "location /" 块

# 3. 启动前端开发服务器:

# cd frontend && npm run dev

# 4. 重启 nginx

# =========================================

# 与前后端的关系

# =========================================

# 部署后架构：

# 用户浏览器

# │

# ▼ http://localhost:80

# ┌──────────────┐

# │ Nginx │ ← 统一入口

# │ :80 │

# └──────┬───────┘

# │

# ┌────┴────────────┐

# ▼ ▼

# ┌─────────┐ ┌───────────┐

# │ 前端 SPA │ │ FastAPI │

# │ 静态文件 │ │ :8004 │

# │ /dist │ │ /api/\* │

# └──────────┘ └───────────┘

# Nginx 将 /api/\* 转发到后端 :8004

# Nginx 将其他路径指向前端 SPA（静态文件）

# 前端 SPA 中的 API 调用现在走相对路径（same-origin），

# 无需配置 CORS

# =========================================

# API 路由映射

# =========================================

# 前端请求 → Nginx → 后端

# ──────────────────────────────────────────────

# GET / 静态文件 → index.html (SPA)

# GET /login 静态文件 → index.html (SPA)

# POST /api/users/login → http://127.0.0.1:8004/api/users/login

# POST /api/users/register → http://127.0.0.1:8004/api/users/register

# POST /api/chat/send → http://127.0.0.1:8004/api/chat/send

# POST /api/chat/stream → http://127.0.0.1:8004/api/chat/stream (SSE)

# GET /api/conversations/ → http://127.0.0.1:8004/api/conversations/

# POST /api/conversations/ → http://127.0.0.1:8004/api/conversations/

# POST /api/knowledge/upload → http://127.0.0.1:8004/api/knowledge/upload

# GET /api/knowledge/docs → http://127.0.0.1:8004/api/knowledge/docs

# GET /api/dashboard/stats → http://127.0.0.1:8004/api/dashboard/stats

# GET /health → http://127.0.0.1:8004/health

# GET /uploads/\* → 直接读取 backend/uploads/ 目录

# =========================================

# 常见问题

# =========================================

# Q: 前端报 net::ERR_CONNECTION_REFUSED

# A: 后端未启动。先启动: cd backend && python main.py

# Q: 页面空白 / 路由刷新后 404

# A: nginx.conf 中没有配置 try_files，缺少 SPA fallback

# Q: SSE 流式输出不更新 / 被缓冲

# A: nginx.conf 中 /api/ 的 location 必须有:

# proxy_buffering off;

# proxy_cache off;

# （已在配置中包含）

# Q: 上传大文件时 413 Request Entity Too Large

# A: 增大 client_max_body_size，nginx.conf 中默认 100M

# Q: CORS 报错

# A: 当 API 和前端同域名时不会有 CORS 问题。

# 如果仍有 CORS 错误，检查后端 main.py 中的 CORS 配置

# （allow_origins=["*"] 默认允许所有来源）
