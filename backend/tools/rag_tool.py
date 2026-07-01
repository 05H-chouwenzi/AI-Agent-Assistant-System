"""
RAG Tool —— 企业内部知识库检索工具（共享）
"""
import time
from tools.base_tool import BaseTool, ToolResult


class RAGTool(BaseTool):
    """
    知识库检索工具 —— 封装已有的 RAG 检索系统

    根据用户问题，从企业内部文档向量库中检索最相关的文档片段。
    """

    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return (
            "搜索企业内部知识库，检索与问题相关的文档、制度、手册、规定等内容。"
            "适用于查询公司内部政策、流程说明、技术文档等已存入知识库的信息。"
            "返回最相关的文档片段及其相关度评分。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要在知识库中搜索的问题或关键词"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回最相关文档数量，默认 5，最大 10",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    def execute(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "").strip()
        top_k = min(kwargs.get("top_k", 5), 10)

        if not query:
            return ToolResult(success=False, error="缺少查询参数", tool_name=self.name)

        start = time.time()
        try:
            from rag.retriever import retrieve

            docs = retrieve(query, top_k=top_k)

            if not docs:
                return ToolResult(
                    success=True,
                    data={"查询": query, "结果": "知识库中暂无相关文档", "文档数": 0},
                    tool_name=self.name,
                )

            formatted = []
            for i, doc in enumerate(docs, 1):
                formatted.append({
                    "序号": i,
                    "相关度": doc.get("score", 0),
                    "来源": doc.get("source", "未知"),
                    "内容": doc.get("content", "")[:500],
                })

            elapsed = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                data={"查询": query, "文档数": len(formatted), "结果": formatted},
                tool_name=self.name,
                execution_time_ms=round(elapsed, 2),
            )

        except ImportError:
            return ToolResult(success=False, error="RAG 检索模块未就绪", tool_name=self.name)
        except Exception as e:
            return ToolResult(success=False, error=f"检索失败: {str(e)}", tool_name=self.name)
