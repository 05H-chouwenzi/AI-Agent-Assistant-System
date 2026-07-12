"""
Agent Nodes 总入口 —— 统一导出所有工作流节点

节点列表：
  - planner_node:    关键词分类器（RAG / Tool / Direct）
  - rag_node:        RAG 知识库检索
  - tool_node:       工具调用（规则优先，LLM 兜底）
  - prompt_builder_node: 构建 LLM 提示词
  - FastRouter:      规则快速路由（零 LLM，部署在 Planner 前）
  - Formatter:       工具结果格式化器（替代 LLM 组织回答）
"""
from agent.nodes.planner import planner_node
from agent.nodes.rag_node import rag_node
from agent.nodes.tool_node import tool_node
from agent.nodes.llm_node import prompt_builder_node, build_prompt
from agent.nodes.fast_router import FastRouter, FastRouteMatch
from agent.nodes.formatter import Formatter

__all__ = [
    "planner_node",
    "rag_node",
    "tool_node",
    "prompt_builder_node",
    "build_prompt",
    "FastRouter",
    "FastRouteMatch",
    "Formatter",
]
