# MULTIMODAL RAG IMPLEMENTATION REPORT

## 1. Modified Files

### Knowledge-base multimodal RAG

| File | Change |
| --- | --- |
| `backend/utils/file_validation.py` | Added shared extension, MIME, signature, size, filename, and file-writing validation for chat attachments and knowledge files. |
| `backend/rag/parsers.py` | Added structured `ParsedBlock` parsers for PDF, DOCX, PPTX, XLSX, XLS, CSV, MD, TXT, JSON, XML, JPG/JPEG/PNG/WEBP. |
| `backend/rag/chunker.py` | Added semantic/structure-aware chunking and unified chunk metadata. |
| `backend/rag/image_understanding.py` | Added Vision LLM semantic image description for knowledge indexing. |
| `backend/services/knowledge_files.py` | Added knowledge upload validation, permanent per-user storage, and background parse/chunk/embed/index flow. |
| `backend/router/knowledge.py` | Replaced synchronous shared-index upload with validated per-user upload, background processing, status polling, user-isolated list/delete. |
| `backend/crud/knowledge_doc.py` | Added optional `user_id` filter to `list_docs`; ownership remains enforced in get/delete. |
| `backend/models/knowledge_doc.py` | Added `error_message` only. |
| `backend/models/knowledge_vector.py` | Added `metadata_json` only. |
| `backend/rag/retriever/__init__.py` | Requires user context and passes `user_id` to the vector store. |
| `backend/rag/vector_store/__init__.py` | Extended the unified vector API with `remove_by_file_id`, legacy metadata backfill, and `user_id` search. |
| `backend/rag/vector_store/faiss_store.py` | Extended FAISS metadata, user filtering, file-id deletion, and legacy metadata backfill without changing the existing shared FAISS design. |
| `backend/rag/vector_store/pgvector_store.py` | Added `metadata_json` persistence, SQL ownership filtering, file-id deletion, and idempotent old-table metadata migration. |
| `backend/tools/rag_tool.py` | Reads request-scoped `user_id`, blocks missing context, filters count queries and semantic retrieval, and exposes multimodal metadata. |
| `backend/router/tools.py` | Wraps direct RAG API calls with request-scoped user context. |
| `backend/config/settings.py` | Reads `PGVECTOR_DATABASE_URL`; retains the existing Vision settings used by chat and knowledge image parsing. |
| `backend/main.py` | Added idempotent startup migration for the two database columns and FAISS legacy metadata backfill. |
| `backend/migrations/003_knowledge_multimodal.sql` | Added `knowledge_docs.error_message`. |
| `backend/migrations/004_knowledge_vector_metadata.sql` | Added `knowledge_vectors.metadata_json` for pgvector. |
| `backend/migrations/apply.py` | Extended the simple MySQL migration runner for the new knowledge migration. |
| `backend/rag/embedding/__init__.py` | Added batch async embedding while retaining `text-embedding-v3`. |
| `backend/rag/loader/__init__.py` | Reused the existing XLSX loader path and closed workbooks to avoid Windows cleanup issues. |
| `backend/requirements.txt` | Added `xlrd>=2.0.1` for legacy `.xls`. |

### Existing chat multimodal integration touched by shared validation

| File | Change |
| --- | --- |
| `backend/api/chat_attachments.py` | Temporary chat attachment upload/delete APIs. |
| `backend/services/chat_attachments.py` | Temporary attachment ownership, validation, parsing, Vision message construction, and cleanup. |
| `backend/api/chat.py`, `backend/api/chat_stream.py`, `backend/api/ws_chat.py` | Accept attachment IDs while preserving normal chat, SSE, and WebSocket response protocols. |
| `backend/agent/graph/state.py`, `backend/agent/graph/nodes.py`, `backend/agent/nodes/fast_router.py`, `backend/agent/llm.py` | Attachments become routing evidence; image-containing requests use the existing Vision-capable LLM path. No Agent node was added or removed. |
| `frontend/src/components/ChatInput.jsx`, `frontend/src/components/ChatMessage.jsx`, `frontend/src/contexts/ChatContext.jsx`, `frontend/src/pages/ChatPage.jsx` | Chat attachment UI and sending; existing chat behavior is unchanged apart from attachment support. |
| `frontend/src/api/chat.js`, `frontend/src/api/ws.js` | Upload/delete and send attachment IDs. |
| `frontend/src/utils/attachments.js` | Shared client-side attachment metadata helpers. |
| `frontend/src/App.css` | Attachment UI styles. |

### Knowledge UI and tests

| File | Change |
| --- | --- |
| `frontend/src/pages/KnowledgePage.jsx` | Multi-file upload, processing/embedding/failed states, status polling, and delete UX. |
| `frontend/src/api/knowledge.js` | Added document status API. |
| `backend/tests/test_knowledge_multimodal.py` | Added parser, chunk metadata, image block, user-context, and FAISS user-isolation tests. |
| `backend/tests/test_chat_attachments.py` | Added attachment validation, parsing, image blocks, and FastRouter behavior tests. |

## 2. Actual Parsers

| Format | Parser / dependency | Extracted structure |
| --- | --- | --- |
| PDF | PyMuPDF | Page text, PDF tables, and embedded images. |
| DOCX | python-docx | Paragraphs, heading hierarchy, tables, and inline images. |
| PPTX | python-pptx | Slide text, titles, tables, and picture shapes. |
| XLSX | openpyxl | Sheet name, headers, and rows grouped by sheet. |
| XLS | xlrd 2.0.2 | Sheet name, headers, rows, and legacy date values. |
| CSV | Python `csv` | Delimiter sniffing, headers, typed rows. |
| MD | Local parser | Heading hierarchy, paragraphs, and code fences. |
| TXT | Local parser | Encoding detection and paragraph splitting. |
| JSON | Python `json` | JSON path aware blocks. |
| XML | Python `xml.etree.ElementTree` | XML path, tag, attributes, text, and child blocks. |
| JPG/JPEG/PNG/WEBP | Existing image loader for OCR plus configured Vision LLM | Image semantic description, detected text/chart data, and image reference. |

Uploads are limited to 20 MB. Binary formats are validated by both MIME and file signature. PDF/DOCX/PPTX-embedded images also go through the same Vision semantic description flow.

## 3. Chunk Scheme

Parsing produces typed `ParsedBlock` objects rather than one opaque string. Every block carries structure metadata such as page, slide, sheet, section, heading, JSON/XML path, image path, and content type.

- Text: paragraphs are preserved and combined up to approximately 1000 characters; an overlong paragraph is split by a fixed character window.
- Tables: rows are grouped into chunks of 50; each chunk repeats the header and preserves row ranges.
- Markdown: heading paths remain attached to the chunk.
- JSON/XML: JSON/XML paths remain attached to the chunk.
- Images: one semantic chunk is produced from the Vision description and retains `image_path` / `image_reference`, OCR text, source filename, page or slide metadata, and `content_type=image`.

Every chunk receives `file_id`, `filename`, `file_type`, `content_type`, `source`, and the other applicable metadata fields before embedding.

## 4. Embedding

- Model: `text-embedding-v3`.
- Provider: existing DashScope OpenAI-compatible endpoint.
- Vector dimension: 1024.
- Indexing: async batch API, up to 10 texts per request.
- Retrieval: async single-text embedding for `RAGTool.aexecute`; synchronous embedding remains available for the sync API path.
- The embedding model was not changed.

## 5. Vector Store

### FAISS

The existing shared `IndexFlatIP` and `documents.pkl` design remains. Vectors are L2-normalized and searched by inner product. `documents.pkl` records now contain structured metadata:

`user_id`, `file_id`, `content_type`, `page_number`, `slide_number`, `sheet_name`, `section_title`, `heading`, `filename`, `file_type`, `source`, and image references when applicable.

Search receives `user_id` from `RAGTool`, skips metadata without the matching owner, and rejects non-positive similarity scores. Deletion removes by `file_id`, with a legacy source fallback only after startup metadata backfill.

### pgvector

`knowledge_vectors` now persists the same chunk metadata in `metadata_json`. Search filters by metadata `user_id`; legacy rows with null metadata remain visible only when their `doc_id` belongs to the requesting user. Deletion uses metadata `file_id` and a legacy `doc_id`/source fallback. On pgvector startup, a missing `metadata_json` column is added idempotently.

## 6. User Isolation

Knowledge files and retrieval are user-isolated at every boundary:

- Upload validation and permanent storage use `backend/uploads/knowledge/<user_id>/<uuid><ext>`.
- `KnowledgeDoc` rows are created with the authenticated `user_id`.
- `GET /api/knowledge/docs` filters by `current_user.id`.
- `GET /api/knowledge/docs/{doc_id}` and `DELETE /api/knowledge/docs/{doc_id}` use ownership-filtered CRUD.
- `RAGTool` obtains `user_id` from request context and fails closed when context is absent.
- `retrieve()` / `aretrieve()` fail closed when `user_id` is missing.
- FAISS and pgvector both filter chunks by owner.
- Knowledge-file processing writes `KnowledgeDoc.user_id` into each vector chunk's metadata.
- FAISS legacy records without `user_id` are hidden. Startup backfill assigns ownership only when the legacy source can match an owned knowledge document.

No implementation relies on the client to send `user_id`.

## 7. Real Image RAG Closed Loop

The verified chain was:

`image upload -> validation/storage -> Vision LLM -> image semantic chunk -> text-embedding-v3 -> FAISS -> user-filtered Retriever/RAGTool -> Research Agent -> Synthesize -> final answer`.

Test setup:

- File: sales chart image, stored as `backend/uploads/knowledge/67/73d219a8bd1544c1becc9db7154c7a92.png`.
- Owner: user ID 67, username `mmrag_823646_0`.
- Knowledge document: ID 83, title `sales_chart.png`, status `completed`.
- Isolation control user: ID 68, username `mmrag_823646_1`.

Vision-derived retrieval content contained:

- Image type: line chart.
- Document title: Sales Performance Report.
- 2024 sales: 1,000 CNY.
- 2025 sales: 800 CNY.
- Change: -20%.
- Trend: sales declined from 2024 to 2025.

Direct RAG API result for user 67 with query `2025年销售额变化`:

- HTTP 200, success true.
- Result count: 1.
- `content_type`: `image`.
- `file_id`: 83.
- Source: `sales_chart.png`.
- Similarity score: 0.638.
- `image_reference`: the actual per-user storage path above.

Agent result through `/api/chat/send` with the research request:

- HTTP 200.
- `task_type`: `graph:general+research`.
- Final answer explicitly cited `sales_chart.png`, file ID 83, content type image, and similarity score 0.6963.
- Final answer reported 2024 sales 1,000 CNY, 2025 sales 800 CNY, a -20% change, and a downward trend.

The two scores differ because the direct verification and the Agent tool call used different embedding queries; both used the same indexed Vision-derived chunk.

User 68 verification:

- Document list: total 0.
- `GET /api/knowledge/docs/83`: HTTP 404.
- RAG query: success true, document count 0, response `知识库中暂无相关文档`.
- Delete document 83: HTTP 404.

After user 67 deleted document 83:

- HTTP 200.
- Removed vectors: 1.
- The test document was cleaned up.

## 8. Test Results

| Verification | Command / method | Result |
| --- | --- | --- |
| Focused backend tests | `python -m pytest backend/tests/test_knowledge_multimodal.py backend/tests/test_chat_attachments.py -q` | 14 passed. |
| Backend syntax | `python -m py_compile ...` for all modified core backend files | Passed. |
| Frontend production build | `npm run build` | Passed; only a chunk-size warning above 500 KB. |
| MySQL compatible columns | SQLAlchemy inspector against the active MySQL database | `knowledge_docs.error_message` exists. The active provider is FAISS, so `knowledge_vectors` is not present in the MySQL database. |
| Real image indexing and retrieval | Live upload, polling, `/api/tools/rag`, and Agent `/api/chat/send` | Passed as documented in section 7. |
| Real cross-user isolation | Live list/get/RAG/delete checks for users 67 and 68 | Passed as documented in section 7. |
| Full backend suite | `python -m pytest backend/tests -q` | 47 tests collected; 29 passed, 18 failed. |
| Frontend lint | `npm run lint --if-present` | Failed: 18 errors and 5 warnings. |

The 18 full-suite failures are concentrated in legacy `backend/tests/test_api.py` cases. Recurring errors are `RuntimeError: Event loop is closed`, plus one external HTTP timeout and one WebSocket test failure. The focused new tests and the live multimodal RAG tests passed.

Frontend lint reports existing React refresh, hook dependency, hook declaration-order, empty-catch, and unused-variable issues in `ChatContext.jsx`, `ChatPage.jsx`, `DashboardPage.jsx`, `KnowledgePage.jsx`, `LogsPage.jsx`, `ToolCenterPage.jsx`, and `router/index.jsx`. This was not treated as a production build failure.

## 9. Agent Architecture

The Agent architecture did not change.

The chain remains:

`FastRouter -> Supervisor -> Worker -> RAG -> Synthesize`.

- FastRouter still handles its direct tool shortcuts.
- Attachment type is evidence for Supervisor routing, not a new Worker.
- Research/Data/General Workers remain `create_react_agent` nodes.
- Workers call the existing RAG tool; RAG now obtains the authenticated user from request context.
- Synthesize remains the final aggregation node.
- No Redis, Celery, MinerU, Docling, Marker, LlamaParse, or new message protocol was introduced.
- Chat SSE and WebSocket payloads were not redesigned; existing attachment metadata remains additive.

The real image RAG Agent call produced `graph:general+research`; this reflects the existing Supervisor/Synthesize behavior rather than a new architecture.

## 10. Known Limitations

1. pgvector was implemented and made schema-compatible, but no real PostgreSQL/pgvector e2e run was possible in this environment because `PGVECTOR_DATABASE_URL` was not configured. The live closed loop used the configured FAISS provider.
2. `.xls` parsing is implemented with `xlrd`, but a real `.xls` upload-to-retrieval e2e was not run.
3. PDF, DOCX, PPTX, XLSX, CSV, MD, TXT, JSON, and XML parsers have focused unit tests, but each format was not individually run through live upload-to-Agent RAG verification.
4. The full legacy backend suite currently fails for reasons outside the focused multimodal tests, mainly event-loop reuse in `test_api.py`; this remains a test-infrastructure limitation to fix separately.
5. Frontend lint currently fails from a mixture of existing hook/React-refresh issues and unused variables. Production build passes.
6. FastAPI `BackgroundTasks` is intentionally used instead of Redis/Celery. If the process exits after upload but before processing, the document can remain in `processing`; there is no automatic retry queue.
7. FAISS remains one shared physical index with logical user filtering. This prevents cross-user content access, but the upload/delete response still reports the global vector count.
8. Vision indexing quality depends on image clarity and the configured Vision model. OCR is only a best-effort hint; unreadable charts can still produce incomplete semantic descriptions.
9. Each standalone image or embedded image becomes one Vision-derived semantic chunk. Very large compound diagrams may require future multi-region indexing for finer recall.
10. Binary formats are enforced at 20 MB and require matching signatures; valid files exceeding the limit are rejected rather than partially indexed.
