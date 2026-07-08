# 🤖 AI Agent Assistant System · 企业 AI 智能助手

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green) ![React](https://img.shields.io/badge/React-19-blueviolet) ![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange)

**企业级 AI 对话助手**，集成知识库（RAG）、外部工具调用、仪表盘监控等核心能力，采用 **FastAPI + LangGraph + React + MySQL** 全栈架构，支持 Docker 一键部署。

---

## 📦 功能概览

| 模块 | 功能 |
|------|------|
| 💬 **智能对话** | 基于大模型的流式对话，支持多轮上下文记忆与 Agent 工作流路由 |
| 📚 **知识库（RAG）** | 上传 PDF / Word / Excel / PPT / TXT / MD / 图片 → 自动解析切块 → 向量化存储（FAISS）→ 检索增强生成 |
| 🛠️ **工具中心** | 可扩展的工具系统：天气查询、数据库查询、HTTP API、RAG 检索；支持 Planner 预选 + 即时路由 |
| 📊 **仪表盘** | 日调用量、Token 消耗、会话统计、知识库文档数、近 7 天趋势图 |
| 🔐 **用户管理** | JWT 鉴权、登录注册、个人资料 |
| 📝 **日志系统** | 全操作日志记录与审计查询 |

## 🧠 Agent 工作流架构

采用 **LangGraph** 构建的状态图驱动架构，通过 **Planner → Router → Executor** 三步完成意图路由：

```
用户输入
   │
   ▼
┌─────────────┐
│  Planner    │ ← 关键词规则匹配，零 LLM 调用，~1ms 决策
│  (分类器)   │
└──────┬──────┘
       │ task_type
       │
  ┌────┼────┬──────────┐
  │    │    │          │
  ▼    ▼    ▼          │
 RAG  Tool Direct ─────┤
  │    │               │
  └────┴───────────────┤
       │               │
       ▼               │
┌─────────────┐        │
│ Prompt      │ ◄──────┘
│ Builder     │ → LLM 组装最终回答
└─────────────┘
```

- **Planner 节点**：基于关键词规则（非 LLM）判断任务类型，延迟 ~1ms
- **RAG 节点**：从 FAISS 向量库检索相关文档片段
- **Tool 节点**：执行 Planner 预选或 ToolRouter 即时路由的外部工具
- **LLM 节点**：将检索结果/工具结果拼装到 Prompt，调用大模型生成最终回答

## 🏗️ 技术栈

### 后端

| 组件 | 技术选型 |
|------|---------|
| 框架 | FastAPI 0.115（异步 Python Web 框架） |
| Agent 编排 | LangGraph 0.2（状态图驱动工作流） |
| 大模型 | 阿里云 DashScope（百炼平台，通义千问系列） |
| ORM | SQLAlchemy 2.0 |
| 数据库 | MySQL 8.0 |
| 向量库 | FAISS（CPU） |
| 文档解析 | PyMuPDF / python-docx / openpyxl / python-pptx / RapidOCR |
| 鉴权 | JWT（python-jose + passlib） |

### 前端

| 组件 | 技术选型 |
|------|---------|
| 框架 | React 19 |
| 构建工具 | Vite 8 |
| 路由 | React Router 7 |
| HTTP 客户端 | Axios |
| 语法 | JavaScript (JSX) |

### DevOps

| 组件 | 工具 |
|------|------|
| 容器化 | Docker Compose（MySQL + Backend + Frontend/Nginx） |
| 反向代理 | Nginx（SPA 路由 + API 代理 + SSE 流式支持） |
| CI/CD | GitHub Actions（自动部署） |

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- MySQL 8.0（或 Docker）
- 阿里云 DashScope API 密钥

### 本地开发

```bash
# 1. 复制环境变量模板并填入真实值
cp .env.example .env

# 2. 启动后端
cd backend
pip install -r requirements.txt
python main.py          # → http://localhost:8000

# 3. 启动前端（另开终端）
cd frontend
npm install
npm run dev             # → http://localhost:5173
```

### Docker 部署

```bash
docker compose up -d --build
# 访问 http://localhost:80
```

### Nginx 生产部署

参考 [nginx-deploy-guide.md](nginx-deploy-guide.md) 配置反向代理、SSL、SSE 流式支持。

## 📁 项目结构

```
├── backend/
│   ├── main.py                # FastAPI 应用入口
│   ├── agent/                 # LangGraph Agent 工作流
│   │   ├── nodes/             #   ├─ planner / rag / tool / llm 节点
│   │   ├── state/             #   ├─ AgentState 状态定义
│   │   └── workflow/          #   └─ 图编排与编译
│   ├── api/                   # API 路由（chat, stream）
│   ├── config/                # 全局配置（读取 .env）
│   ├── crud/                  # 数据库 CRUD 操作
│   ├── database/              # 数据库会话与引擎管理
│   ├── models/                # SQLAlchemy 数据模型
│   ├── rag/                   # RAG 全链路
│   │   ├── loader/            #   文档解析（PDF/DOCX/图片等）
│   │   ├── splitter/          #   文本切块
│   │   ├── embedding/         #   向量化（DashScope Embedding）
│   │   ├── vector_store/      #   FAISS 向量索引存储
│   │   └── retriever/         #   语义检索
│   ├── router/                # 业务路由（用户/会话/知识库/日志/仪表盘）
│   ├── schemas/               # Pydantic 请求/响应模型
│   ├── services/              # LLM 服务封装（流式 + 非流式）
│   ├── tools/                 # 工具注册中心 & 内置工具实现
│   ├── utils/                 # 工具函数（鉴权、异常处理）
│   └── migrations/            # 数据库迁移脚本
├── frontend/
│   └── src/
│       ├── pages/             # 页面组件（登录/聊天/知识库/工具/日志等）
│       ├── components/        # 通用 UI 组件
│       ├── api/               # API 客户端封装
│       ├── hooks/             # 自定义 Hooks
│       └── router/            # 路由配置
├── docker-compose.yml         # Docker 编排文件
├── nginx.conf                 # Nginx 反向代理配置
└── .env.example               # 环境变量模板
```

## 🔧 可扩展工具系统

工具基于 `BaseTool` 抽象类，实现 `execute()` 方法即可注册：

```python
from tools.base_tool import BaseTool, ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"

    def execute(self, **kwargs) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, data="结果")
```

内置工具：`WeatherTool`（天气查询） · `MySQLTool`（数据库查询） · `HttpTool`（HTTP 请求） · `RAGTool`（知识库检索）

## 🧪 知识库 RAG 流程

```
上传文档 → 格式解析（PDF/DOCX/XLSX/PPTX/TXT/MD/图片）
         → 文本切块（chunk）
         → Embedding 向量化（DashScope）
         → FAISS 索引存储
         ──────────────────────────
用户提问 → 语义检索 top-k 相关块
         → 拼入 Prompt → LLM 生成回答
```

## 📄 License

MIT

---

> **项目状态**：MVP v0.1.0 · 持续迭代中
