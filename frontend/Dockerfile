# Python 3.11
FROM python:3.11.9-slim-bookworm

# =========================
# 环境变量
# =========================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 工作目录
WORKDIR /app

# =========================
# 更换 Debian 软件源（可选）
# =========================
RUN sed -i 's/deb.debian.org/mirrors.cloud.tencent.com/g' \
    /etc/apt/sources.list.d/debian.sources || true

# =========================
# 安装系统依赖
# =========================
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# =========================
# 安装 Python 依赖
# =========================
COPY requirements.txt .

RUN python -m pip install --upgrade pip && \
    pip install -i https://mirrors.cloud.tencent.com/pypi/simple \
    --trusted-host mirrors.cloud.tencent.com \
    -r requirements.txt

# =========================
# 复制项目
# =========================
COPY . .

# =========================
# 创建运行目录
# =========================
RUN mkdir -p \
    uploads \
    logs \
    rag/data

# =========================
# 暴露端口
# =========================
EXPOSE 8000

# =========================
# 启动 FastAPI
# =========================
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]