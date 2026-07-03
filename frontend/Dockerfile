# =============================================================================
# Frontend Dockerfile — 多阶段构建
# 阶段 1: 用 Node 构建 React 项目
# 阶段 2: 用 Nginx 提供静态文件
#
# 构建上下文：项目根目录 (.)
# 所有前端源码路径相对于项目根目录为 frontend/
# =============================================================================

# ---- 阶段 1：构建 ----
FROM node:20-alpine AS build

WORKDIR /app

# 利用 Docker 层缓存：先复制依赖文件，装完再复制源码
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ---- 阶段 2：运行 ----
FROM nginx:alpine

# 复制构建产物到 nginx 静态目录
COPY --from=build /app/dist /usr/share/nginx/html

# 复制自定义 nginx 配置（Docker 版）
COPY nginx.docker.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
