import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AppSidebar from "../components/AppSidebar";
import { getDashboardStats, getDashboardTrends, getDashboardSystem } from "../api/dashboard";

function TrendChart({ data, dataKey, label, color, format }) {
  if (!data || data.length === 0) return null;
  const values = data.map((d) => d[dataKey]);
  const max = Math.max(...values, 1);

  return (
    <div className="trend-chart">
      <h4 className="trend-chart-title">{label}</h4>
      <div className="trend-bars">
        {data.map((d, i) => (
          <div className="trend-bar-col" key={i}>
            <div className="trend-bar-value" style={{ color }}>
              {d[dataKey]}
            </div>
            <div
              className="trend-bar"
              style={{
                height: `${(d[dataKey] / max) * 100}%`,
                background: color,
              }}
            />
            <div className="trend-bar-label">{d.date}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [stats, setStats] = useState(null);
  const [trends, setTrends] = useState(null);
  const [system, setSystem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      getDashboardStats().then(setStats),
      getDashboardTrends().then(setTrends),
      getDashboardSystem().then(setSystem),
    ]).then((results) => {
      const newErrors = {};
      if (results[0].status === "rejected") {
        const err = results[0].reason;
        newErrors.stats = err.response?.data?.detail || (err.code === "ECONNABORTED" ? "请求超时，请刷新重试" : err.message) || "获取统计数据失败";
      }
      if (results[1].status === "rejected") {
        const err = results[1].reason;
        newErrors.trends = err.response?.data?.detail || (err.code === "ECONNABORTED" ? "请求超时，请刷新重试" : err.message) || "获取趋势数据失败";
      }
      if (results[2].status === "rejected") {
        const err = results[2].reason;
        newErrors.system = err.response?.data?.detail || (err.code === "ECONNABORTED" ? "请求超时，请刷新重试" : err.message) || "获取系统状态失败";
      }
      setErrors(newErrors);
      setLoading(false);
    });
  }, []);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="dashboard-container">
          <div className="page-header">
            <h2>📊 Dashboard</h2>
            <p className="page-subtitle">系统概览与关键指标</p>
          </div>

        {loading ? (
          <div className="dashboard-loading">
            <div className="spinner" />
            <span>加载中...</span>
          </div>
        ) : (
          <>
            {/* ========== 统计卡片区 ========== */}
            <div className="dashboard-grid">
              <div className="stat-card">
                <div className="stat-icon">💬</div>
                <div className="stat-info">
                  <span className="stat-value">{stats?.today_call_count ?? 0}</span>
                  <span className="stat-label">今日调用</span>
                  {stats?.today_tokens > 0 && (
                    <span className="stat-sub">{stats.today_tokens} tokens</span>
                  )}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">🗂</div>
                <div className="stat-info">
                  <span className="stat-value">{stats?.total_conversations ?? 0}</span>
                  <span className="stat-label">总对话数</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">✉️</div>
                <div className="stat-info">
                  <span className="stat-value">{stats?.total_messages ?? 0}</span>
                  <span className="stat-label">总消息数</span>
                  {stats?.user_msg_count > 0 && (
                    <span className="stat-sub">
                      用户 {stats.user_msg_count} / AI {stats.assistant_msg_count}
                    </span>
                  )}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">📚</div>
                <div className="stat-info">
                  <span className="stat-value">{stats?.doc_count ?? 0}</span>
                  <span className="stat-label">知识库文档</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-icon">🛠</div>
                <div className="stat-info">
                  <span className="stat-value">{stats?.tool_count ?? 0}</span>
                  <span className="stat-label">工具</span>
                </div>
              </div>
            </div>

            {/* ========== 双栏：趋势图 + 系统/聊天 ========== */}
            <div className="dashboard-two-col">
              {/* 左栏：本周趋势 */}
              <div className="dashboard-section">
                <h3>📈 本周趋势</h3>
                {errors.trends ? (
                  <p className="text-muted" style={{ textAlign: "center", padding: "24px" }}>
                    {errors.trends}
                  </p>
                ) : trends ? (
                  <div className="trend-charts-row">
                    <TrendChart
                      data={trends.daily_messages}
                      dataKey="count"
                      label="每日消息数"
                      color="#2563eb"
                    />
                    <TrendChart
                      data={trends.daily_tokens}
                      dataKey="tokens"
                      label="Token 消耗"
                      color="#8b5cf6"
                    />
                  </div>
                ) : (
                  <p className="text-muted" style={{ textAlign: "center", padding: "24px" }}>
                    暂无趋势数据
                  </p>
                )}
              </div>

              {/* 右栏：系统状态 + 最近聊天 */}
              <div className="dashboard-right-col">
                {/* 系统状态 */}
                <div className="dashboard-section system-status-section">
                  <h3>🤖 系统状态</h3>
                  {errors.system ? (
                    <p className="text-muted" style={{ textAlign: "center", padding: "16px" }}>
                      {errors.system}
                    </p>
                  ) : system ? (
                    <div className="system-status-grid">
                      <div className="status-row">
                        <span className="status-label">数据库</span>
                        <span className={`status-dot ${system.db_status === "connected" ? "online" : "offline"}`} />
                        <span className="status-text">{system.db_status === "connected" ? "已连接" : "断开"}</span>
                      </div>
                      <div className="status-row">
                        <span className="status-label">系统版本</span>
                        <span className="status-value">{system.version}</span>
                      </div>
                      <div className="status-row">
                        <span className="status-label">当前模型</span>
                        <span className="status-value model-badge">{system.model}</span>
                      </div>
                      <div className="status-row">
                        <span className="status-label">服务器时间</span>
                        <span className="status-value">{system.server_time}</span>
                      </div>
                      {system.last_log_summary?.length > 0 && (
                        <div className="status-logs">
                          <div className="status-label">最近日志</div>
                          <div className="status-log-list">
                            {system.last_log_summary.map((log) => (
                              <div className="status-log-item" key={log.id}>
                                <span className={`log-level-badge ${log.level}`}>{log.level}</span>
                                <span className="log-module">{log.module}</span>
                                <span className="log-msg">{log.message}</span>
                                <span className="log-time">{log.time}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-muted" style={{ textAlign: "center", padding: "16px" }}>
                      暂无系统信息
                    </p>
                  )}
                </div>

                {/* 最近聊天 */}
                <div className="dashboard-section">
                  <h3>📋 最近聊天</h3>
                  {stats?.recent_conversations?.length > 0 ? (
                    <ul className="recent-conv-list">
                      {stats.recent_conversations.map((conv) => (
                        <li
                          key={conv.id}
                          className="recent-conv-item"
                          onClick={() => navigate(`/chat?conv=${conv.id}`)}
                        >
                          <div className="recent-conv-content">
                            <div className="recent-conv-title">{conv.title}</div>
                            <div className="recent-conv-msg">{conv.last_message || "（暂无消息）"}</div>
                          </div>
                          <span className="recent-conv-time">{conv.last_time}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted" style={{ textAlign: "center", padding: "24px" }}>
                      暂无聊天记录
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
        </div> {/* dashboard-container */}
      </div>
    </AppSidebar>
  );
}
