import { useState, useEffect, useRef } from "react";
import AppSidebar from "../components/AppSidebar";
import ConfirmDialog from "../components/ConfirmDialog";
import FileIcon from "../components/FileIcon";
import { uploadDoc, listDocs, deleteDoc } from "../api/knowledge";

export default function KnowledgePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState(null);
  const fileRef = useRef();
  const [confirm, setConfirm] = useState({ open: false, id: null, title: "" });

  useEffect(() => {
    fetchDocs();
  }, [page]);

  async function fetchDocs() {
    setLoading(true);
    try {
      const data = await listDocs({ page, page_size: 20 });
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

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const res = await uploadDoc(file);
      showMsg(`${res.title} 上传成功（${res.chunks} 个文本块）`);
      setPage(1);
      await fetchDocs();
    } catch (err) {
      showMsg(err.response?.data?.detail || "上传失败", "error");
    }
    setUploading(false);
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

  const totalPages = Math.ceil(total / 20);

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
              const file = e.dataTransfer.files?.[0];
              if (!file) return;
              setUploading(true);
              try {
                const res = await uploadDoc(file);
                showMsg(`${res.title} 上传成功（${res.chunks} 个文本块）`);
                setPage(1);
                await fetchDocs();
              } catch (err) {
                showMsg(err.response?.data?.detail || "上传失败", "error");
              }
              setUploading(false);
            }}
          >
            <div className="upload-icon">{uploading ? "⏳" : "📄"}</div>
            <p>{uploading ? "正在上传并处理..." : "拖拽文件到此处上传，或点击选择文件"}</p>
            <p className="text-muted" style={{ fontSize: "13px", marginTop: "8px" }}>
              支持 PDF · Word · Excel · PPT · Markdown · TXT · 图片(PNG/JPG)
            </p>
            <button className="upload-btn" disabled={uploading}>
              {uploading ? "处理中..." : "选择文件"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.txt,.md,.markdown,.docx,.xlsx,.xls,.pptx,.png,.jpg,.jpeg,.bmp,.tiff,.webp"
              style={{ display: "none" }}
              onChange={handleFileChange}
            />
          </div>

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
                      <span className="doc-status completed">已完成</span>
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
