# AI Agent Assistant System - Enterprise AI Assistant
![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-19-blueviolet)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange)

Enterprise AI conversation assistant with RAG knowledge base, external tool calling, dashboard monitoring, and multi-agent orchestration. Built with FastAPI + LangGraph + React + MySQL.

## Agent Workflow Architecture

Two-layer design: FastRouter (zero-LLM bypass) + LangGraph cyclic graph with Supervisor loop.

`mermaid
flowchart TD
    USER[User Input] --> FastRouter
    subgraph L1 [Layer 1: FastRouter]
        FR[FastRouter - Rule Match] -->|Hit| Direct[Execute Tool Directly]
        FR -->|Miss| Graph
    end
    subgraph L2 [Layer 2: LangGraph Cyclic Graph]
        Supervisor[Supervisor - LLM Routing] -->|research| R[Research - Knowledge]
        Supervisor -->|data| D[Data - SQL & Analysis]
        Supervisor -->|general| G[General - Q&A]
        Supervisor -->|FINISH| Check{Synthesize?}
        R --> Loop{Steps < 6?}
        D --> Loop
        G --> Loop
        Loop -->|Yes| Supervisor
        Loop -->|No| Check
        Check -->|1 Worker| END
        Check -->|>=2 Workers| Syn[Synthesize - Aggregate]
    end
    Syn --> Final[Final Answer]
    END --> Final
`

### FastRouter

Pure regex rule matching, zero LLM, ~1ms latency. Covers weather, calculator, greeting, datetime.

### LangGraph Cyclic Graph

- **Supervisor**: Always calls LLM for routing, heuristic fallback for parse failures
- **Workers** (research/data/general): create\_react\_agent with cached instances, streaming=True
- **Synthesize**: Aggregates multi-Worker results into final answer
- **Safety**: Max 6 steps, auto-detect repeated routing

Reference: [WL7749/ai-agent](https://github.com/WL7749/ai-agent)

## Quick Start

`ash
cp .env.example .env
cd backend && pip install -r requirements.txt && python main.py
cd frontend && npm install && npm run dev
`

## Tech Stack

Backend: FastAPI, LangGraph, SQLAlchemy, MySQL, FAISS
Frontend: React 19, Vite 8, React Router 7, Axios
DevOps: Docker Compose, Nginx, GitHub Actions

## License: MIT
