"""
Response Node —— 格式化最终输出
"""
from agent.state.agent_state import AgentState

def response_node(state:AgentState)->AgentState:
    """整合最终结果返回"""
    return state