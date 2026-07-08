# =============================================================================
# frontend/Dockerfile — 多阶段构建
#   阶段1: 用 Node 编译 React SPA
#   阶段2: 用 Nginx 运行静态文件
# =============================================================================

# ---- 阶段1: 构建前端 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 安装依赖（单独 copy package.json 以利用 Docker 缓存）
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# 构建
COPY frontend/ ./
RUN npm run build

# ---- 阶段2: Nginx 运行 ----
FROM nginx:alpine

# 拷贝 Nginx 配置
COPY nginx.docker.conf /etc/nginx/nginx.conf

# 拷贝构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
