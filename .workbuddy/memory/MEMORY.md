# 项目记忆 - AI Agent Assistant System

## 架构
- FastAPI + LangGraph + React + MySQL + FAISS(DashScope Embedding)
- LLM: DeepSeek (api.deepseek.com) via LLM_API_KEY/LLM_BASE_URL/LLM_MODEL
- Embedding: DashScope text-embedding-v3 (DASHSCOPE_API_KEY)
- Agent: supervisor(启发式路由) → create_react_agent(research/data/general) → END
- 流式: SSE (chat_stream.py) / WebSocket (ws_chat.py)
- 旁路: FastRouter 规则匹配(零LLM)

## 性能问题修复进度 (2026-07-20 核实)
- P0 已修复: SSE双重执行BUG(改检查graph_events_received) / Worker流式LLM(get_llm streaming=True) / WebSocket真流式(astream_events)
- P1 已修复: FAISS内存缓存(写操作后清缓存)
- P1 部分修复: Embedding有aembed_text异步版但同步版仍存在 / MySQL同步路径用SQLAlchemy连接池但异步仍新建pymysql / Weather有aexecute异步版
- P1 未修复: HTTP工具仍同步urllib / ToolRouter仍新建OpenAI客户端
- P2 未修复: direct_llm.py极简架构仍未接入主流程

## 代码质量问题 (2026-07-20 评估)
- 死代码: FastRouter._match_weather_bare 定义但未调用
- 冗余: ToolRouter LLM路由与create_react_agent function calling重复
- 未集成: direct_llm.py 完整实现但未接入任何主流程
- 测试不足: 仅test_api.py + test_cases.sh, 无单元测试CI
- 多租户名存实亡: FAISS索引共享(vector_index_shared), 无租户隔离
- 鉴权用同步DB会话(get_current_user), 阻塞事件循环

## 技术偏好
- 参考项目: ai-qa-community (WL7749) 极简架构，1秒响应
- 用户关注响应速度，希望对标参考项目的性能
