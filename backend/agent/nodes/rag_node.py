"""
RAG Node —— 知识库检索节点
"""
from agent.state.agent_state import AgentState

def rag_node(state:AgentState)->AgentState:
    """从知识库检索相关文档片段"""
    question=state["question"]

    # MVP 阶段用模拟数据，后面接真实 FAISS 检索
    mock_docs=[f"知识库检索结果: 关于[{question}]的相关文档片段..."]
    
    state["retrieved_docs"]=mock_docs
    return state

