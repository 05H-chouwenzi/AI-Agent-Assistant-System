# =============================================================================
# Backend Dockerfile - FastAPI 后端服务
# =============================================================================
FROM python:3.11-slim AS backend

WORKDIR /app

# 安装编译依赖（faiss-cpu 和 rapidocr-onnxruntime 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    cmake \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY . .

# 创建必要目录
RUN mkdir -p uploads rag/data

EXPOSE 8000

# 生产模式启动（去掉 --reload）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
