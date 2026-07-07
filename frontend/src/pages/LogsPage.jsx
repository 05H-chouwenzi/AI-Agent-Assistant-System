import { useState, useEffect } from "react";
import AppSidebar from "../components/AppSidebar";
import { getLogs } from "../api/logs";

// ===== 日志级别风格（与 Dashboard 一致）=====
const LEVEL_STYLES = {
  info:    { bg: "#dbeafe", color: "#1d4ed8", label: "INFO" },
  warning: { bg: "#fef3c7", color: "#b45309", label: "WARN" },
  error:   { bg: "#fef2f2", color: "#dc2626", label: "ERROR" },
  system:  { bg: "#f3f4f6", color: "#6b7280", label: "SYS" },
};

// ===== 模块中文标签（简化版）=====
const MODULE_LABELS = {
  agent: "Agent",
  chat: "聊天",
  tool: "工具调用",
};

// ===== 操作分类中文标签 =====
const ACTION_LABELS = {
  "user.login": "登录", "user.register": "注册",
  "user.profile_update": "修改资料", "user.password_change": "修改密码",
  "chat.ask": "AI 提问", "chat.ask_stream": "AI 提问(流)",
  "rag.search": "智能检索", "rag.search_direct": "智能检索(API)",
  "tool.weather": "天气查询", "tool.mysql": "数据库查询", "tool.http": "HTTP 请求",
  "knowledge.upload": "上传文档", "knowledge.delete": "删除文档", "knowledge.list": "文档列表",
  "conversation.create": "创建会话", "conversation.delete": "删除会话",
  "conversation.view": "查看消息", "conversation.list": "会话列表",
};

// ===== 操作图标 =====
const ACTION_ICONS = {
  "user.login": "🔑", "user.register": "📝",
  "chat.ask": "💬", "chat.ask_stream": "⚡",
  "rag.search": "📚", "rag.search_direct": "📚",
  "tool.weather": "🌤", "tool.mysql": "🗄", "tool.http": "🌐",
  "knowledge.upload": "📄", "knowledge.delete": "🗑", "knowledge.list": "📋",
  "conversation.create": "➕", "conversation.delete": "➖",
  "conversation.view": "👁", "conversation.list": "📑",
};

// ===== 模块列表（过滤用）=====
const MODULE_LIST = Object.keys(MODULE_LABELS);

export default function LogsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [moduleFilter, setModuleFilter] = useState("");

  useEffect(() => {
    setPage(1);
  }, [moduleFilter]);

  useEffect(() => {
    fetchLogs();
  }, [page, moduleFilter]);

  async function fetchLogs() {
    setLoading(true);
    try {
      const params = { page, page_size: 20 };
      if (moduleFilter) params.module = moduleFilter;
      const data = await getLogs(params);
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      setLogs([]);
    }
    setLoading(false);
  }

  const totalPages = Math.ceil(total / 20);
  const logListEl = logs.length === 0 ? (
    <div className="empty-state">暂无操作日志</div>
  ) : (
    <>
      <div className="log-list">
        {logs.map((log) => {
          const levelStyle = LEVEL_STYLES[log.level] || LEVEL_STYLES.system;
          const actionLabel = ACTION_LABELS[log.action] || log.action || log.module;
          const actionIcon = ACTION_ICONS[log.action] || "📌";
          return (
            <div key={log.id} className="log-row">
              {/* 左侧：级别 + 操作标签 */}
              <div className="log-row-left">
                <span className="badge badge-level" style={{ background: levelStyle.bg, color: levelStyle.color }}>
                  {levelStyle.label}
                </span>
                <span className="badge badge-action">
                  {actionIcon} {actionLabel}
                </span>
              </div>

              {/* 中间：消息 + 元信息 */}
              <div className="log-row-body">
                <div className="log-row-msg">{log.message}</div>
                <div className="log-row-meta">
                  {log.username && (
                    <span className="meta-tag meta-user">👤 {log.username}</span>
                  )}
                  {log.ip_address && (
                    <span className="meta-tag meta-ip">🌐 {log.ip_address}</span>
                  )}
                  {log.execution_time_ms != null && (
                    <span className="meta-tag meta-ms">⏱ {log.execution_time_ms}ms</span>
                  )}
                  {log.resource_type && (
                    <span className="meta-tag meta-resource">
                      📦 {log.resource_type}{log.resource_id ? ` #${log.resource_id}` : ""}
                    </span>
                  )}
                </div>
              </div>

              {/* 右侧：时间 */}
              <div className="log-row-time">
                {log.time?.slice(0, 19).replace("T", " ")}
              </div>
            </div>
          );
        })}
      </div>

      {/* 分页 */}
      <div className="log-pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>← 上一页</button>
        <span>{page} / {totalPages || 1}</span>
        <button disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页 →</button>
      </div>
    </>
  );

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        {/* ===== 页面标题 ===== */}
        <div className="page-header">
          <h2>📜 操作日志</h2>
          <p className="page-subtitle">记录用户的所有操作行为，支持分类筛选与审计追溯</p>
        </div>

        <div className="page-body">
          {/* ===== 统计栏 ===== */}
          <div className="log-stats-bar">
            <div className="log-stat-item">
              <span className="log-stat-value">{total}</span>
              <span className="log-stat-label">总记录</span>
            </div>
            <div className="log-stat-item">
              <span className="log-stat-value">{page}</span>
              <span className="log-stat-label">当前页</span>
            </div>
            <div className="log-stat-divider" />
            <button className="log-refresh-btn" onClick={fetchLogs} disabled={loading}>
              {loading ? "⟳ 加载中..." : "↻ 刷新"}
            </button>
          </div>

          {/* ===== 过滤栏 ===== */}
          <div className="log-filters">
            <div className="log-filter-group">
              <span className="log-filter-label">模块</span>
              <div className="log-filter-pills">
                <button
                  className={`log-filter-pill ${!moduleFilter ? "active" : ""}`}
                  onClick={() => setModuleFilter("")}
                >全部</button>
                {MODULE_LIST.map((m) => (
                  <button
                    key={m}
                    className={`log-filter-pill ${moduleFilter === m ? "active" : ""}`}
                    onClick={() => setModuleFilter(moduleFilter === m ? "" : m)}
                  >{MODULE_LABELS[m]}</button>
                ))}
              </div>
            </div>
          </div>

          {/* ===== 日志列表 ===== */}
          <div className="section-card" style={{ marginTop: 20, marginLeft: 0, marginRight: 0 }}>
            {loading ? (
              <div className="dashboard-loading">
                <div className="spinner" />
                <span>加载中...</span>
              </div>
            ) : logListEl}
          </div>
        </div>
      </div>

      {/* ============ 内联样式 ============ */}
      <style>{`
        .log-stats-bar {
          display: flex;
          align-items: center;
          gap: 20px;
          padding: 16px 20px;
          background: #f9fafb;
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          margin-bottom: 16px;
        }
        .log-stat-item {
          display: flex;
          align-items: baseline;
          gap: 6px;
        }
        .log-stat-value {
          font-size: 22px;
          font-weight: 700;
          color: var(--text);
          line-height: 1;
        }
        .log-stat-label {
          font-size: 12px;
          color: var(--text-muted);
        }
        .log-stat-divider {
          width: 1px;
          height: 28px;
          background: var(--border);
          flex-shrink: 0;
        }
        .log-refresh-btn {
          margin-left: auto;
          padding: 6px 16px;
          border-radius: 8px;
          font-size: 13px;
          border: 1px solid var(--border);
          background: #fff;
          color: var(--text-secondary);
          cursor: pointer;
          transition: all .15s;
        }
        .log-refresh-btn:hover:not(:disabled) {
          background: #f3f4f6;
          border-color: #d1d5db;
        }
        .log-refresh-btn:disabled {
          opacity: .5;
          cursor: default;
        }

        /* ── 过滤栏 ── */
        .log-filters {
          display: flex;
          flex-direction: column;
          gap: 10px;
          background: #fff;
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 16px 20px;
        }
        .log-filter-group {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }
        .log-filter-label {
          font-size: 12px;
          font-weight: 600;
          color: var(--text-secondary);
          min-width: 36px;
          padding-top: 6px;
          flex-shrink: 0;
        }
        .log-filter-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }
        .log-filter-pill {
          padding: 4px 12px;
          border-radius: 20px;
          font-size: 12px;
          border: 1px solid var(--border);
          background: #fff;
          color: var(--text-secondary);
          cursor: pointer;
          transition: all .15s;
          white-space: nowrap;
        }
        .log-filter-pill:hover {
          background: #f3f4f6;
          border-color: #d1d5db;
        }
        .log-filter-pill.active {
          background: var(--sidebar-bg);
          color: #fff;
          border-color: var(--sidebar-bg);
        }
        .log-filter-pill-action {
          font-size: 12px;
        }

        /* ── 日志行 ── */
        .log-row {
          display: flex;
          align-items: flex-start;
          gap: 14px;
          padding: 12px 16px;
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          transition: background .15s, border-color .15s;
        }
        .log-row:hover {
          background: #fafbfc;
          border-color: #d1d5db;
        }
        .log-row-left {
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 80px;
          flex-shrink: 0;
        }
        .log-row-body {
          flex: 1;
          min-width: 0;
        }
        .log-row-msg {
          font-size: 14px;
          color: var(--text);
          line-height: 1.5;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .log-row-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 6px;
        }
        .meta-tag {
          font-size: 11px;
          padding: 1px 8px;
          border-radius: 4px;
          color: var(--text-muted);
          background: #f3f4f6;
          white-space: nowrap;
        }
        .meta-user { background: #f0f4ff; color: #1d4ed8; }
        .meta-ip { background: #f0fdf4; color: #15803d; }
        .meta-ms { background: #fefce8; color: #a16207; }
        .meta-resource { background: #faf5ff; color: #7e22ce; }
        .log-row-time {
          font-size: 11px;
          color: var(--text-muted);
          white-space: nowrap;
          flex-shrink: 0;
          padding-top: 2px;
        }

        /* ── 通用徽章 ── */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 3px;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 600;
          white-space: nowrap;
          flex-shrink: 0;
        }
        .badge-level {
          letter-spacing: .3px;
        }
        .badge-action {
          background: #eef2ff;
          color: #4338ca;
          font-weight: 500;
        }

        /* ── 空状态 ── */
        .empty-state {
          text-align: center;
          padding: 48px 20px;
          color: var(--text-muted);
          font-size: 14px;
        }

        /* ── 覆盖 section-card ── */
        .section-card .log-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .section-card .empty-state + .log-pagination { display: none; }
      `}</style>
    </AppSidebar>
  );
}
