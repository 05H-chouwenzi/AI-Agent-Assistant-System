import { useState, useEffect } from "react";
import AppSidebar from "../components/AppSidebar";
import { getLogs } from "../api/logs";

const LEVEL_COLORS = {
  info: "#2563eb",
  warning: "#d97706",
  error: "#ef4444",
  system: "#6b7280",
};

const MODULE_LABELS = {
  agent: "Agent",
  rag: "RAG",
  tool: "工具",
  api: "API",
  system: "系统",
};

export default function LogsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchLogs();
  }, [page]);

  async function fetchLogs() {
    setLoading(true);
    try {
      const data = await getLogs({ page, page_size: 20 });
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      setLogs([]);
    }
    setLoading(false);
  }

  const totalPages = Math.ceil(total / 20);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>📜 System Logs</h2></div>
        <div className="page-body">
          <div className="section-card">
            {loading ? (
              <p className="text-muted" style={{ textAlign: "center", padding: 24 }}>加载中...</p>
            ) : logs.length === 0 ? (
              <p className="text-muted" style={{ textAlign: "center", padding: 24 }}>暂无日志</p>
            ) : (
              <>
                <div className="log-list">
                  {logs.map((log) => (
                    <div key={log.id} className="log-item">
                      <span className="log-badge" style={{ background: LEVEL_COLORS[log.level] || "#6b7280" }}>
                        {log.level}
                      </span>
                      <span className="log-module">{MODULE_LABELS[log.module] || log.module}</span>
                      <span className="log-message">{log.message}</span>
                      <span className="log-time">{log.time?.slice(0, 19).replace("T", " ")}</span>
                    </div>
                  ))}
                </div>

                {/* 分页 */}
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
    </AppSidebar>
  );
}
