"""
RAG Node —— 知识库检索节点（共享知识库）
"""
from agent.state.agent_state import AgentState
from rag.retriever import retrieve


def rag_node(state: AgentState) -> AgentState:
    """从共享知识库检索相关文档片段"""
    question = state["question"]

    docs = retrieve(question, top_k=3)

    if docs:
        snippets = [f"[相关度 {d['score']}] {d['content']}" for d in docs]
        state["retrieved_docs"] = snippets
    else:
        state["retrieved_docs"] = ["知识库暂无相关文档"]
    return state
