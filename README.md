# AI Agent Assistant System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Fast.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-Streaming-blue.svg" alt="LangGraph">
  <img src="https://img.shields.io/badge/React-18+-green.svg" alt="React">
</p>

一个面向中小团队的 AI Agent 助手平台，包含规则路由、LangGraph 工作流、RAG 检索、SSE Token Streaming 和请求级性能监控。

## 当前架构

```text
用户请求
  |
  +-- FastRouter 命中规则 --> Tool --> 直接返回
  |
  +-- 未命中 --> Supervisor --> Research / Data / General --> END
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
* 按工具名统计的调用次数与耗时
* 实际路由历史

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

也可以使用 Docker：

```bash
docker-compose up -d
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

## 更新日志

### v1.2.2 - 2026-09-03

* 修正 TTFT 统计：只统计请求开始到第一个用户可见 SSE Token。
* 增加请求级 Agent 节点耗时、LLM 调用次数和 Tool 调用统计。
* 修复嵌套 `create_react_agent` 事件归属，恢复连续 Token Streaming。
* 移除零 Token 场景下重复执行整个 Graph 的回退逻辑。
* 避免 Supervisor、Tool 参数或多个 Worker 内部输出重复展示。

### v1.2.1 - 2026-09-03

* 引入基于 `astream_events` 的 Token 流式输出。
* 优化 Supervisor 路由和 Worker 结束逻辑。
* 增加基础性能监控模块。
