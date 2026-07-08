# ===========================
# Base Image
# ===========================
FROM python:3.11-slim

# 防止 Python 生成 pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1

# 实时输出日志
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ===========================
# 安装系统依赖
# ===========================
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    cmake \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ===========================
# 安装 Python 依赖（利用 Docker 缓存）
# requirements.txt 不变时不会重新安装
# ===========================
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install \
    -i https://pypi.org/simple \
    --no-cache-dir \
    -r requirements.txt

# ===========================
# 复制项目源码
# ===========================
COPY . .

# ===========================
# 创建运行目录
# ===========================
RUN mkdir -p \
    uploads \
    rag/data \
    logs

# ===========================
# 暴露端口
# ===========================
EXPOSE 8000

# ===========================
# 启动服务
# ===========================
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]