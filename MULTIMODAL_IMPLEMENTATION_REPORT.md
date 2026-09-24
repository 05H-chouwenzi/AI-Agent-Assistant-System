# 多模态功能实现报告

## 1. 修改文件

| 文件路径 | 修改内容 |
| --- | --- |
| `backend/services/chat_attachments.py` | 新增聊天临时附件的保存、校验、解析、多模态消息构建、所有权校验、TTL/请求结束清理。 |
| `backend/api/chat_attachments.py` | 新增 `POST /api/chat/attachments` 与 `DELETE /api/chat/attachments/{attachment_id}`。 |
| `backend/api/chat.py` | `/api/chat/send` 支持 `attachment_ids`，构建真实附件消息，请求结束后清理临时文件。 |
| `backend/api/chat_stream.py` | `/api/chat/stream` 支持 `attachment_ids`，保持 SSE Token Streaming，请求结束后清理临时文件。 |
| `backend/api/ws_chat.py` | WebSocket 消息支持 `attachment_ids`，保持原 WS Token Streaming / route / tool / done 协议。 |
| `backend/agent/graph/state.py` | `AgentState` 增加 `attachments` 元数据字段。 |
| `backend/agent/graph/nodes.py` | Supervisor 使用附件类型作为路由证据；含图片 Worker 使用 Vision LLM；Synthesize 在含图片时也使用 Vision LLM。 |
| `backend/agent/nodes/fast_router.py` | 带附件请求不再命中直接 Tool 旁路，统一进入 Supervisor/Worker。 |
| `backend/agent/llm.py` | 新增独立的 `get_vision_llm()`，不替换现有文本模型。 |
| `backend/config/settings.py` | 新增 `VISION_LLM_API_KEY`、`VISION_LLM_BASE_URL`、`VISION_LLM_MODEL` 配置。 |
| `backend/main.py` | 注册聊天附件路由。 |
| `backend/rag/loader/__init__.py` | 复用现有 XLSX 解析器并补上 `workbook.close()`，避免 Windows 临时文件删除失败。 |
| `backend/requirements.txt` | 增加 `xlrd>=2.0.1` 用于旧版 `.xls`。 |
| `.env.example` | 增加 Vision 模型配置示例。 |
| `frontend/src/utils/attachments.js` | 前端附件扩展名、大小、类型标签与格式化工具。 |
| `frontend/src/api/chat.js` | 新增聊天附件上传/删除 API。 |
| `frontend/src/api/ws.js` | `sendChatMessage` 可发送 `attachment_ids`。 |
| `frontend/src/components/ChatInput.jsx` | 聊天输入框增加“+”附件按钮、拖拽、粘贴图片、附件卡片、删除附件、上传/错误状态。 |
| `frontend/src/components/ChatMessage.jsx` | 用户消息展示附件卡片和图片缩略图。 |
| `frontend/src/contexts/ChatContext.jsx` | 发送链路携带附件元数据与 `attachment_ids`。 |
| `frontend/src/pages/ChatPage.jsx` | 原 PDF 快捷上传改为真正先上传附件再发送。 |
| `frontend/src/App.css` | 附件卡片、缩略图、拖拽状态与错误提示样式。 |
| `backend/tests/test_chat_attachments.py` | 新增附件安全校验、多类型解析、图片内容块、多附件、FastRouter 旁路测试。 |

## 2. 新增能力

- Drag & Drop 上传。
- Ctrl+V 图片粘贴。
- 图片缩略图与文档/表格附件预览。
- 附件删除。
- PDF、DOCX、PPTX。
- XLSX、XLS、CSV。
- JPG/JPEG/PNG/WEBP。
- TXT、MD、JSON、XML。
- 附件类型自动识别与 `AttachmentContext`。
- 聊天临时附件处理，不写入 Knowledge Base。
- 图片以 `image_url` 内容块进入 Vision LLM。

支持上限：

- 单附件 20MB。
- 每条消息最多 5 个附件。
- 不支持音频、视频。

## 3. Agent 如何识别附件

实际链路如下：

```text
用户
↓
前端只选择文件并上传：POST /api/chat/attachments
↓
前端发送 message + attachment_ids（不决定 Research/Data/Vision）
↓
后端 load_attachments() 校验用户身份、所有权、数量、扩展名、MIME、签名、大小
↓
build_chat_message() 生成：
  图片 -> image_url 内容块
  PDF/DOCX/PPTX -> 结构化文本
  XLSX/XLS/CSV -> Sheet/列名/行数据结构
  TXT/MD/JSON/XML -> 结构化文本
↓
AgentState.attachments = [{filename, extension, mime_type, size, kind, source}]
↓
FastRouter
  无附件：保留原直接 Tool 规则
  有附件：返回 None，强制进入 Supervisor/Worker
↓
Supervisor
  table 附件增强 Data 证据
  document 附件增强 Research 证据
  image 附件增强 General 证据
↓
Research / Data / General Worker
  Worker 逻辑不变
  如存在图片，调用 Vision-capable LLM
↓
必要时 Synthesize
↓
Streaming
```

没有新增 Supervisor、Worker、Planner、Critic 或 Memory Agent。

## 4. 图片如何进入 LLM

当前真实实现：

1. `services/chat_attachments.build_chat_message()` 读取图片二进制。
2. 图片被转成 base64 Data URI。
3. 构造 LangChain/OpenAI 兼容内容块：

```json
[
  { "type": "text", "text": "描述一下这张图片\n\n用户上传了 1 个聊天临时附件..." },
  { "type": "image_url", "image_url": { "url": "data:image/png;base64,..." } }
]
```

4. `agent/graph/nodes._run_worker()` 检测到 `kind == "image"` 后，选择 `vision:research` / `vision:data` / `vision:general` 对应的 Worker Agent。
5. Vision LLM 由 `agent/llm.get_vision_llm()` 创建，使用 `langchain_openai.ChatOpenAI`，请求 DashScope OpenAI-compatible endpoint。

当前模型配置：

- 原文本模型仍是 `.env` 中的 `LLM_MODEL=deepseek-chat` / `https://api.deepseek.com`，未被替换。
- 图片模型默认使用 `VISION_LLM_MODEL=qwen-vl-max`。
- Vision 默认 Base URL 是 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
- `VISION_LLM_API_KEY` 未配置时，默认回落使用已有 `DASHSCOPE_API_KEY`。

已实测：

```text
请求：请描述这张图片 + red background / blue circle PNG
路由：graph:general
模型输出：这张图片展示了一个红色背景上的蓝色圆形。
```

SSE 也实测到逐 Token 输出，说明图片不是只发送文件名。

## 5. 文档如何处理

PDF / DOCX / PPTX 直接复用现有 `backend/rag/loader`：

| 类型 | 实际调用 |
| --- | --- |
| PDF | `rag.loader.load_pdf()` |
| DOCX | `rag.loader.load_docx()` |
| PPTX | `rag.loader.load_pptx()` |

文本/结构化类型：

| 类型 | 实际调用 |
| --- | --- |
| TXT | `rag.loader.load_document()` fallback 到 `load_txt()`，自动尝试 UTF-8 / GBK / GB18030 / UTF-16 |
| MD | `rag.loader.load_md()` |
| JSON | `chat_attachments._parse_json()`，使用 `json.load()` 后以 `json.dumps(..., indent=2)` 保留结构 |
| XML | `chat_attachments._parse_xml()`，使用 `xml.etree.ElementTree` 后格式化输出 |

所有非图片解析结果最多单个附件 12,000 字符，单条消息附件文本总量最多 40,000 字符，超出时明确标注“附件内容已截断”。

聊天附件不会被切块、向量化或写入 `knowledge_docs`。知识库上传仍走原来的 `/api/knowledge/upload`。

## 6. 表格如何处理

| 类型 | 实际调用 |
| --- | --- |
| XLSX | `rag.loader.load_xlsx()`，输出 Sheet 名与逐行数据；本次补了 `wb.close()` |
| XLS | `chat_attachments._parse_xls()`，使用 `xlrd` 输出 Sheet 名、行数、列数与前 200 行数据 |
| CSV | `chat_attachments._parse_csv()`，使用标准库 `csv.DictReader` 输出 `columns / row_count / rows` |

表格不会简单丢失结构；解析结果保留列名和行对象。Supervisor 看到 `kind == "table"` 会增加 Data 证据。Data Worker 仍使用原 `create_react_agent` 与现有工具体系。

## 7. Streaming 是否保持

保持。

- WebSocket 路由仍是 `/api/ws/chat/{conversation_id}`，原消息协议仍发送 `token / route / tool_start / tool_end / title_update / done / ping / error`。本次只是在入站 JSON 中兼容 `attachment_ids`。
- SSE 路由仍是 `/api/chat/stream`，仍使用 `agent_graph.astream_events(version="v2")`、keepalive 和原 `chunk / done / error` 事件。
- 没有把 WebSocket 改成 SSE，也没有重写 LangGraph Streaming。

已用真实图片请求实测 SSE：

```text
data: {"type": "chunk", "content": "这张"}
data: {"type": "chunk", "content": "图片"}
data: {"type": "chunk", "content": "展示"}
...
```

## 8. Agent 架构是否改变

没有改变架构。

保留：

```text
FastRouter
↓
Supervisor
↓
Research / Data / General Worker
↓
Tool / RAG
↓
必要时继续 Supervisor
↓
Synthesize
↓
END
```

`AgentState.attachments` 只是输入元数据。附件类型只作为 Supervisor 的路由证据；Worker 类型、图结构、工具注册、RAG、Synthesize 均未重构。

## 9. 数据库是否修改

未修改数据库结构。

没有新增 migration、字段或附件表。消息保存行为保持原有 `messages.content` / `messages.role`。附件仅在请求生命周期内保存在：

```text
backend/uploads/chat_attachments/<user_id>/<uuid><extension>
```

## 10. 测试结果

新增单测：

```text
backend/tests/test_chat_attachments.py
7 passed
```

| 用例 | 结果 | 验证方式 |
| --- | --- | --- |
| 普通聊天 | PASS | 本地 `/api/chat/send` 发送“你好”，FastRouter 正常返回。 |
| 图片 | PASS | 本地 `/api/chat/send` 发送红底蓝圆 PNG，Qwen-VL 输出正确描述；非流式和 SSE 均验证。 |
| PDF | PASS | 验证扩展名/MIME/签名校验与现有 `load_pdf()` 接入；未额外跑真实 LLM 总结。 |
| DOCX | PASS | 单测生成 DOCX，断言解析出段落内容。 |
| PPTX | PASS | 单测生成 PPTX，断言 Slide、标题、正文。 |
| XLSX | PASS | 单测生成 XLSX，断言 Sheet 名与行数据。 |
| XLS | PASS | 接入 `xlrd` 并安装 `xlrd 2.0.2`；未额外生成真实 BIFF 样本做 LLM 端到端。 |
| CSV | PASS | 单测断言 columns、employee、sales、rows。 |
| TXT | PASS | 上传接口与 `load_txt()` fallback 链路验证。 |
| MD | PASS | 单测断言 Markdown 文本。 |
| JSON | PASS | 单测断言保留 JSON key/value 结构。 |
| XML | PASS | 单测断言保留 XML 标签结构。 |
| 多附件 | PASS | 单测图片 + CSV 同时构造消息；本地实测 PDF/CSV 之外的图片 + CSV 请求正确路由 Data 并识别 Alice 销售额最高。 |
| 拖拽 | PASS | `ChatInput` 已实现 dragenter/dragover/drop、preventDefault、校验、卡片；前端构建通过。 |
| 粘贴图片 | PASS | `ChatInput` 的 `onPaste` 拦截图片 File，不破坏普通文字粘贴；前端构建通过。 |
| 删除附件 | PASS | 单元/接口验证前端删除与 `DELETE /api/chat/attachments/{id}`；发送列表会移除该附件。 |
| 不支持类型 | PASS | 单测 `.mp4` 上传被拒绝；前端也先提示“不支持的文件类型”。 |
| 请求结束清理 | PASS | `/send` 与 `/stream` 使用 finally 清理；WebSocket done 后清理；另有 1 小时 TTL。 |

其他验证：

| 命令 | 结果 |
| --- | --- |
| `python -m py_compile ...` | PASS |
| `python -m pytest tests/test_chat_attachments.py -q` | PASS，7 passed |
| `npm run build` | PASS |
| `npm run lint` | FAIL，但失败点是仓库既有 ESLint 规则问题和无关页面警告；本次新增代码可构建。 |
| `pytest tests -m "not slow"` | 部分既有用例失败，主要是 `test_api.py` 会话级 `client` fixture 在 Windows/event loop 下的既有问题、外部工具超时、Dashboard 断言旧值；新增附件测试 7/7 通过。 |

## 11. 已知限制

1. 当前文本模型仍是 DeepSeek `deepseek-chat`，不支持 Vision；图片会切换到独立的 Qwen-VL，不会把图片喂给 DeepSeek。
2. 在“图片 + CSV”同时路由到 Data Worker 的实测中，表格分析正确，但 Qwen-VL 的 tool-calling 工作流没有对图片内容做额外确认。纯图片请求已确认能真正读图；混合任务里的图片理解依赖 Qwen-VL 对 tool-calling 消息的支持，复杂组合建议优先纯图片或纯表格。
3. 图片进入 LLM 采用 base64 Data URI，20MB 图片会产生较大的请求体；当前已限制单文件 20MB、单消息 5 个附件。
4. PDF 只提取文本，不做扫描件 OCR；扫描 PDF 可能返回空文本。
5. PPTX 只提取标题、段落等文字；PPT 内嵌图片不会走 OCR 或 Vision。
6. XLSX/XLS 解析前 200 行内容，超过后会被截断。
7. 表格复杂计算仍由 Data Worker 与 LLM 推理完成；本实现没有引入新的 DataFrame 计算引擎。
8. 请求异常断开时，WebSocket 可能来不及执行 finally；这类孤儿文件由 1 小时 TTL 兜底。
9. 前端未跑 Playwright 截图级 UI 测试；拖拽/粘贴是代码实现与 Vite 构建验证。
