"""
Planner Node —— 判断任务类型
"""
from agent.state.agent_state import AgentState
from services.llm_service import call_llm

PLAN_PROMPT = """你是一个任务分类助手。根据用户问题，判断应该走哪条路线，只回复一个单词。

规则：
- 如果问题涉及企业内部制度、规定、手册、文档、知识库 → 回复 rag
- 如果问题需要查询外部实时数据（天气、股票、新闻等）→ 回复 tool
- 其他一般性问题 → 回复 direct

只回复 rag、tool 或 direct，不要加任何其他内容。"""

def planner_node(state: AgentState) -> AgentState:
    """用 LLM 判断用户问题是走 RAG、Tool 还是直接 LLM"""
    question = state["question"]

    result = call_llm(PLAN_PROMPT, question).strip().lower()

    if result not in ("rag", "tool", "direct"):
        result = "direct"

    state["task_type"] = result
    return state

