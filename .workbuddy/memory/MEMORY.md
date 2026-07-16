# 项目记忆 - AI Agent Assistant System

## 架构
- FastAPI + LangGraph + React + MySQL + FAISS(DashScope Embedding)
- LLM: DeepSeek (api.deepseek.com) via LLM_API_KEY/LLM_BASE_URL/LLM_MODEL
- Embedding: DashScope text-embedding-v3 (DASHSCOPE_API_KEY)
- Agent: supervisor(启发式路由) → create_react_agent(research/data/general) → END
- 流式: SSE (chat_stream.py) / WebSocket (ws_chat.py)
- 旁路: FastRouter 规则匹配(零LLM)

## 已知性能问题 (2026-07-15 分析)
- P0: chat_stream.py 双重图执行BUG + Worker非流式LLM
- P1: FAISS磁盘读/Embedding同步阻塞/MySQL无连接池/工具同步IO/ToolRouter新建客户端
- services/direct_llm.py 已实现极简流式架构(对标ai-qa-community)但未接入主流程

## 技术偏好
- 参考项目: ai-qa-community (WL7749) 极简架构，1秒响应
- 用户关注响应速度，希望对标参考项目的性能
