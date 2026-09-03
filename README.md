# AI Agent Assistant System - 企业级 AI 助手平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-Fast.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18+-green.svg" alt="React">
</p>

---

## 🚀 项目简介

一个**企业级智能任务处理系统**,基于 **Multi-Agent 架构**和 **Agent Workflow Graph**,实现任务智能路由、分布式执行与高效协同。

### ✨ 核心特性

* Multi-Agent 协作框架 (Supervisor-Worker)
* **Token Streaming** (stream_events + on_llm_new_token) 真正的字级实时流式输出
* 智能工作流路由 (FastRouter + Supervisor)
* 本地优先 RAG (ChromaDB)
* 全链路性能监控

---

## 📦 快速开始

\\\ash
cp .env.example .env
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm run dev
\\\

Or use Docker:
\\\ash
docker-compose up -d
\\\

---

## 🏗️ 系统架构

| 模块 | 路径 | 说明 |
|------|------|------|
| Agent Core | backend/agent/ | Multi-Agent 图计算引擎 |
| Router | backend/router/ | FastRouter + Supervisor |
| RAG | backend/rag/ | 向量数据库 + 语义检索 |
| Frontend | frontend/src/ | React + TypeScript |

---

## 🚀 性能优化成果

| 指标 | 优化前 | 优化后 | 提升 |
|-----|--------|--------|------|
| Token(简单) | 基准 | ↓70-94% | 🚀 |
| Token(复杂) | 基准 | ↓50-70% | 🚀 |
| TTFT | N/A | 300-800ms | ⚡ |
| LLM 调用 | 每次 | 0-1 次 | 💰 |
| Graph | Bug | 修复 | 🔒 |

---

## 📝 更新日志

### v1.2.1 (2026-09-03) - Token Streaming 真实化

✅ **P0**: 真正 Token Streaming (on_llm_new_token)  
   - 从 \stream_mode=\"updates\"\ 改为 \stream_events(version=\"v2\")\  
   - 监听 \on_llm_new_token\ 事件而非 \on_chat_model_stream\  
   - 前端体验：字级实时流式输出，类似 ChatGPT  

✅ P1: Worker edges 修复 | 删除重执行降级  
✅ P1: 双阈值策略 | 降权机制 | Same Worker 检测 | 上下文优化 | temp=0  
✅ P2: 性能监控模块 monitor.py

---

<div align="center">
**Happy Coding! 🚀**  
**Made with ❤️ by 你雄哥**
</div>
