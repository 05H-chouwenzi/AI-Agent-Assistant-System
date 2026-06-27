"""
Tool Node —— 外部工具调用节点
"""
from agent.state.agent_state import AgentState

def tool_node(state:AgentState)->AgentState:
    """调用外部工具获取结果"""
    question=state["question"]
    # MVP 阶段用模拟数据，后面接真实工具
    if "天气" in question or "weather" in question:
        result="工具返回:当前天气晴朗,气温25°C"
    else:
        result=f"工具返回:已查询[{question}]"

    state["tool_result"]=result
    return state
