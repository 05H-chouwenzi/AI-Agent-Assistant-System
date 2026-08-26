"""
RAG Tool —— 企业内部知识库检索工具（共享）
"""
import re
import time
import asyncio
from tools.base_tool import BaseTool, ToolResult

# 文件数量类问题：直接统计 knowledge_docs，而不是做语义检索
_COUNT_PATTERNS = [
    r'(?:知识库|文档|文件|资料).{0,8}(?:几个|多少|几篇|几份|数量|总数)',
    r'(?:几个|多少|几篇|几份).{0,8}(?:文件|文档|资料)',
    r'(?:文件|文档|资料)(?:的?数量|总数|数)',
    r'(?:有多少|共有多少|一共多少).{0,8}(?:文件|文档|资料)',
    # 列举/清单意图（LLM 常把"有几个文件"改写为"文件列表/文档目录"）
    r'(?:知识库).{0,6}(?:文件|文档)(?:列表|清单|目录)',
    r'(?:文件|文档)(?:列表|清单|目录|有哪些|都有什么|有什么)',
]


def _is_count_query(query: str) -> bool:
    q = query.strip()
    if not q:
        return False
    return any(re.search(p, q) for p in _COUNT_PATTERNS)


def _count_knowledge_docs() -> dict:
    """统计知识库文件数量（knowledge_docs 表），并附带标题列表"""
    from database.session import engine
    from sqlalchemy import text as sa_text
    try:
        with engine.connect() as conn:
            total = conn.execute(sa_text("SELECT COUNT(*) FROM knowledge_docs")).scalar()
            rows = conn.execute(
                sa_text("SELECT title FROM knowledge_docs ORDER BY id DESC LIMIT 20")
            ).fetchall()
        return {
            "文件总数": int(total or 0),
            "文件列表": [r[0] for r in rows],
        }
    except Exception as e:
        return {"文件总数": -1, "错误": str(e)}


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

        # 文件/文档数量类问题：直接统计 knowledge_docs 表
        if _is_count_query(query):
            count_info = _count_knowledge_docs()
            if count_info.get("文件总数", -1) >= 0:
                total = count_info["文件总数"]
                titles = count_info.get("文件列表", [])
                result_text = f"知识库中共有 {total} 个文件。"
                if titles:
                    result_text += " 文件标题：" + "；".join(titles[:20])
                return ToolResult(
                    success=True,
                    data={"查询": query, "结果": result_text, "文件总数": total, "文件列表": titles},
                    tool_name=self.name,
                )

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

    async def aexecute(self, **kwargs) -> ToolResult:
        """异步版本：使用 AsyncOpenAI embedding，真正不阻塞事件循环"""
        query = kwargs.get("query", "").strip()
        top_k = min(kwargs.get("top_k", 5), 10)

        if not query:
            return ToolResult(success=False, error="缺少查询参数", tool_name=self.name)

        # 文件/文档数量类问题：直接统计 knowledge_docs 表（无需 embedding）
        if _is_count_query(query):
            count_info = await asyncio.to_thread(_count_knowledge_docs)
            if count_info.get("文件总数", -1) >= 0:
                total = count_info["文件总数"]
                titles = count_info.get("文件列表", [])
                result_text = f"知识库中共有 {total} 个文件。"
                if titles:
                    result_text += " 文件标题：" + "；".join(titles[:20])
                return ToolResult(
                    success=True,
                    data={"查询": query, "结果": result_text, "文件总数": total, "文件列表": titles},
                    tool_name=self.name,
                )

        start = time.time()
        try:
            from rag.retriever import aretrieve

            docs = await aretrieve(query, top_k=top_k)

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
