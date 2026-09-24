import { useState, useEffect, useRef } from "react";
import AppSidebar from "../components/AppSidebar";
import ConfirmDialog from "../components/ConfirmDialog";
import FileIcon from "../components/FileIcon";
import { uploadDoc, listDocs, deleteDoc, getDocStatus } from "../api/knowledge";
import { isSupportedAttachment, formatFileSize } from "../utils/attachments";

const DOCS_PAGE_SIZE = 10;

export default function KnowledgePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);
  const [uploadItems, setUploadItems] = useState([]);
  const fileRef = useRef();
  const [confirm, setConfirm] = useState({ open: false, id: null, title: "" });

  useEffect(() => {
    fetchDocs();
  }, [page]);

  async function fetchDocs() {
    setLoading(true);
    try {
      const data = await listDocs({ page, page_size: DOCS_PAGE_SIZE });
      setDocs(data.items);
      setTotal(data.total);
    } catch {
      setDocs([]);
    }
    setLoading(false);
  }

  function showMsg(text, type = "success") {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 3000);
  }

  function setUploadItem(key, patch) {
    setUploadItems((items) => items.map((item) => (item.key === key ? { ...item, ...patch } : item)));
  }

  async function pollStatus(key, id) {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const status = await getDocStatus(id);
      setUploadItem(key, { status: status.status, error: status.error_message });
      if (status.status === "completed" || status.status === "failed") return status;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    return null;
  }

  async function uploadOne(file) {
    const key = `${file.name}-${file.size}-${file.lastModified}-${Math.random()}`;
    if (!isSupportedAttachment(file)) {
      setUploadItems((items) => [...items, {
        key,
        name: file.name,
        size: file.size,
        status: "failed",
        error: "不支持的文件类型",
      }]);
      return;
    }
    setUploadItems((items) => [...items, {
      key,
      name: file.name,
      size: file.size,
      status: "uploading",
    }]);
    try {
      const res = await uploadDoc(file);
      setUploadItem(key, { status: res.status || "processing" });
      const finalStatus = await pollStatus(key, res.id);
      setUploadItem(key, {
        status: finalStatus?.status || "failed",
        error: finalStatus?.error_message || (finalStatus ? "" : "处理超时"),
      });
      await fetchDocs();
    } catch (err) {
      setUploadItem(key, {
        status: "failed",
        error: err.response?.data?.detail || "上传失败",
      });
    }
  }

  async function handleFiles(fileList) {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setUploading(true);
    await Promise.all(files.map(uploadOne));
    setUploading(false);
    setPage(1);
    await fetchDocs();
  }

  async function handleFileChange(e) {
    await handleFiles(e.target.files);
    e.target.value = "";
  }

  function handleDelete(id, title) {
    setConfirm({ open: true, id, title });
  }

  async function confirmDelete() {
    try {
      await deleteDoc(confirm.id);
      showMsg("删除成功");
      setConfirm({ open: false, id: null, title: "" });
      await fetchDocs();
    } catch {
      showMsg("删除失败", "error");
      setConfirm({ open: false, id: null, title: "" });
    }
  }

  const totalPages = Math.ceil(total / DOCS_PAGE_SIZE);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>📚 Company Knowledge Base</h2></div>
        <div className="page-body">
          {msg && (
            <div className={`toast ${msg.type === "error" ? "toast-error" : ""}`}>
              {msg.text}
            </div>
          )}

          <div
            className="upload-area"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={async (e) => {
              e.preventDefault();
              await handleFiles(e.dataTransfer.files);
            }}
          >
            <div className="upload-icon">{uploading ? "⏳" : "📄"}</div>
            <p>{uploading ? "正在上传并处理..." : "拖拽文件到此处上传，或点击选择文件"}</p>
            <p className="text-muted" style={{ fontSize: "13px", marginTop: "8px" }}>
              支持 PDF · DOCX · PPTX · XLSX · XLS · CSV · MD · TXT · JSON · XML · JPG/JPEG/PNG/WEBP
            </p>
            <button className="upload-btn" disabled={uploading}>
              {uploading ? "处理中..." : "选择文件"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.pptx,.xlsx,.xls,.csv,.txt,.md,.json,.xml,.jpg,.jpeg,.png,.webp"
              multiple
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
          </div>

          {uploadItems.length > 0 && (
            <div className="upload-items">
              {uploadItems.map((item) => (
                <div key={item.key} className="upload-item">
                  <span className="upload-item-name">{item.name}</span>
                  <span className="text-muted">{formatFileSize(item.size)}</span>
                  <span className={`doc-status ${item.status}`}>
                    {item.status === "uploading" && "上传中"}
                    {item.status === "processing" && "解析中"}
                    {item.status === "embedding" && "向量化中"}
                    {item.status === "completed" && "已完成"}
                    {item.status === "failed" && "失败"}
                  </span>
                  {item.error && <span className="upload-item-error">{item.error}</span>}
                </div>
              ))}
            </div>
          )}

          <div className="section-card" style={{ marginTop: "24px" }}>
            <h3>已上传文档（{total}）</h3>
            {loading ? (
              <p className="text-muted" style={{ textAlign: "center", padding: "24px" }}>加载中...</p>
            ) : docs.length === 0 ? (
              <p className="text-muted" style={{ textAlign: "center", padding: "24px" }}>
                暂无文档
              </p>
            ) : (
              <>
                <div className="doc-list">
                  {docs.map((d) => (
                    <div key={d.id} className="doc-item">
                      <span className="doc-icon">
                        <FileIcon type={d.file_type} />
                      </span>
                      <span className="doc-title">{d.title}</span>
                      <span className={`doc-status ${d.status}`}>
                        {d.status === "processing" && "解析中"}
                        {d.status === "embedding" && "向量化中"}
                        {d.status === "completed" && "已完成"}
                        {d.status === "failed" && "失败"}
                        {!["processing", "embedding", "completed", "failed"].includes(d.status) && d.status}
                      </span>
                      <span className="doc-uploader" title="上传者">{d.uploader}</span>
                      <span className="doc-date">{d.created_at?.slice(0, 10)}</span>
                      <button className="doc-delete" onClick={() => handleDelete(d.id, d.title)}>
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>
                <div className="log-pagination">
                  <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
                  <span>{page} / {totalPages || 1}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页</button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirm.open}
        title="删除文档"
        message={`确定删除「${confirm.title}」？删除后无法恢复。`}
        onCancel={() => setConfirm({ open: false, id: null, title: "" })}
        onConfirm={confirmDelete}
      />
    </AppSidebar>
  );
}
