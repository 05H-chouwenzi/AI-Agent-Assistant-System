# AI Agent Assistant System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Fast.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-Streaming-blue.svg" alt="LangGraph">
  <img src="https://img.shields.io/badge/React-19+-green.svg" alt="React">
</p>

一个面向中小团队的 AI Agent 助手平台，包含规则路由、LangGraph 工作流、RAG 检索、SSE Token Streaming、请求级性能监控、用户与权限、知识库管理、会话历史和工具中心。

## 功能特性

* Agent 工作流：FastRouter 规则旁路、Supervisor 调度、Research / Data / General 协作。
* RAG 检索：文档上传、切分、向量索引和语义召回，支持 FAISS 与 pgvector。
* 流式输出：基于 LangGraph 事件流的 Token Streaming，避免等待完整结果。
* 消息渲染：AI 回复支持 Markdown 标题、加粗、列表、表格和代码块。
* 性能监控：请求级 TTFT、节点耗时、LLM 调用次数、Tool 调用统计和路由历史。
* 应用能力：用户登录、会话管理、知识库、工具中心、日志和仪表盘。
* 启动预热：应用启动时预编译 Worker Agent，降低首次请求延迟。

## 当前架构

```mermaid
flowchart TB
    User["用户输入"]

    subgraph Layer1["Layer 1: FastRouter"]
        direction TB
        FR["FastRouter<br/>规则/关键词快速匹配<br/>零 LLM 调用"]
        Tool["直接执行工具<br/>Weather / Calculator /<br/>Greeting / DateTime"]
        FR -- "命中" --> Tool
    end

    subgraph Layer2["Layer 2: LangGraph 循环图"]
        direction TB
        SUP["Supervisor 节点<br/>启发式路由"]

        RW["Research Worker<br/>知识检索 Agent"]
        DW["Data Worker<br/>SQL 数据分析 Agent"]
        GW["General Worker<br/>通用问答 Agent"]

        STEP{"step_count < 2?"}
        SYNQ{"需要 Synthesize?"}
        SYN["Synthesize Node<br/>聚合多 Worker 结果"]
        FINAL["最终回答"]

        SUP -- "research" --> RW
        SUP -- "data" --> DW
        SUP -- "general" --> GW
        RW --> STEP
        DW --> STEP
        GW --> STEP
        STEP -- "是" --> SUP
        STEP -- "否" --> SYNQ
        SYNQ -- "1 个 Worker" --> FINAL
        SYNQ -- "≥2 个不同 Worker" --> SYN
        SYN --> FINAL
    end

    Return["返回用户"]

    User --> Layer1
    Layer1 -- "命中" --> Return
    Layer1 -- "未命中" --> Layer2
    Layer2 --> Return
```

当前主流程保持轻量：FastRouter 是零 LLM 调用的规则旁路；Supervisor 使用启发式路由；Worker 使用带工具的 ReAct Agent。没有新增 Planner、Reflection 或 Critic。

## Token Streaming

流式链路基于 LangGraph 的 `astream_events(version="v2")`：

```text
LLM Token
  -> LangGraph on_chat_model_stream
  -> 外层 Agent 节点归属解析
  -> SSE chunk
  -> 前端
```

Supervisor 的内部输出和 Tool 参数不会推送给前端；用户只收到当前可见节点的最终回答 Token。

## 请求级性能监控

每个流式请求会创建独立的 `PerformanceMonitor`。日志以首个用户可见 SSE chunk 作为 TTFT 终点：

```text
TTFT = first_user_visible_token - request_start
```

示例日志：

```yaml
[AgentMetrics]
RequestStart: 2026-09-03 14:02:41.414000
FirstUserVisibleToken: 2026-09-03 14:02:42.488000
TTFT: 1073ms
Total: 13187ms
FirstTokenSource: research

Node Time:
  fast_router: 0ms
  supervisor: 1ms
  research: 13173ms
  data: 0ms
  general: 0ms
  synthesize: 0ms

LLM Calls:
  supervisor: 0
  research: 2
  data: 0
  general: 0
  synthesize: 0
  Total: 2

Tool Calls:
  rag_search: 2 (7956ms)

Route History: research
```

监控内容覆盖：

* 真实用户可见 TTFT
* FastRouter / Supervisor / Worker / Tool 耗时
* Supervisor、Research、Data、General、Synthesize 的 LLM 调用次数
* Supervisor、Research、Data、General、Synthesize 的 LLM 调用耗时
* 按工具名统计的调用次数与耗时
* 实际路由历史

启动阶段会执行 `warm_up_agents()`，提前构建 Research / Data / General Worker Agent，避免第一个用户请求承担 Agent 初始化成本。

## 环境变量

先复制 `.env.example` 为 `.env`，再补充以下关键配置：

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | MySQL 连接地址，Docker 内通常使用 `db:3306` |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API Key，用于向量 Embedding |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 聊天模型配置，未配置时回退到 DashScope |
| `JWT_SECRET` | 登录态签名密钥，生产环境必须使用强随机值 |
| `CORS_ORIGINS` | 允许的前端来源，多个来源用英文逗号分隔 |
| `VECTOR_STORE_PROVIDER` | 向量存储类型，可选 `faiss` 或 `pgvector` |

## 快速开始

1. 准备环境变量：

```bash
cp .env.example .env
```

2. 启动后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

3. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

4. 生产构建前端：

```bash
cd frontend
npm run build
```

也可以使用 Docker：

```bash
docker-compose up -d --build
```

Compose 暴露的端口：

| 服务 | 地址 |
|------|------|
| Frontend / Nginx | `http://localhost` |
| MySQL | `127.0.0.1:3307` |
| pgvector | 默认不启动，启用 profile 后为 `127.0.0.1:5433` |

如果要使用 pgvector 替代 FAISS，先在 `.env` 中设置：

```bash
VECTOR_STORE_PROVIDER=pgvector
PGVECTOR_DATABASE_URL=postgresql+psycopg2://pgvector:你的密码@pgvector-db:5432/ai_assistant
```

再启动可选服务：

```bash
docker-compose --profile pgvector up -d
```

## 目录结构

| 模块 | 路径 | 说明 |
|------|------|------|
| API | `backend/api` | SSE 聊天、WebSocket、业务接口 |
| Agent | `backend/agent` | LangGraph 节点、路由和性能监控 |
| Tools | `backend/tools` | RAG、数据库、天气、计算等工具 |
| RAG | `backend/rag` | 文档加载、切分、向量检索 |
| Frontend | `frontend/src` | React + TypeScript 聊天界面 |

## 测试

```bash
cd backend
python -m pytest tests/test_agent_metrics.py -q
```
