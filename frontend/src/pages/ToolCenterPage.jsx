import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import AppSidebar from "../components/AppSidebar";
import FileIcon from "../components/FileIcon";
import { queryWeather, executeDatabaseQuery, sendHttpRequest } from "../api/tools";
import { listDocs } from "../api/knowledge";

const TOOLS = [
  { name: "RAG", label: "知识库检索", desc: "搜索企业内部知识库与文档", icon: "📚", tool: "rag_search" },
  { name: "HTTP API", label: "HTTP 请求", desc: "调用外部 HTTP 接口获取数据", icon: "🌐", tool: "http" },
  { name: "Database", label: "数据库查询", desc: "查询 MySQL 企业业务数据", icon: "🗄", tool: "mysql" },
  { name: "Weather", label: "天气查询", desc: "查询全球城市的实时天气与未来预报", icon: "🌤", tool: "weather" },
];

export default function ToolCenterPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTool, setActiveTool] = useState(null);
  const [city, setCity] = useState("");
  const [days, setDays] = useState(1);
  const [weatherResult, setWeatherResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [searchParams] = useSearchParams();

  useEffect(() => {
    const tool = searchParams.get("tool");
    if (tool) {
      setActiveTool(tool);
    }
  }, [searchParams]);

  // 进入 RAG 工具时获取文档列表
  useEffect(() => {
    if (activeTool === "rag_search") {
      fetchDocs();
    }
  }, [activeTool]);

  // 数据库查询状态
  const [dbQuery, setDbQuery] = useState("");
  const [dbLimit, setDbLimit] = useState(50);
  const [dbResult, setDbResult] = useState(null);
  const [dbLoading, setDbLoading] = useState(false);
  const [dbError, setDbError] = useState("");

  // HTTP 请求状态
  const [httpUrl, setHttpUrl] = useState("");
  const [httpMethod, setHttpMethod] = useState("GET");
  const [httpHeaders, setHttpHeaders] = useState("");
  const [httpBody, setHttpBody] = useState("");
  const [httpResult, setHttpResult] = useState(null);
  const [httpLoading, setHttpLoading] = useState(false);
  const [httpError, setHttpError] = useState("");

  // RAG 知识库文档列表状态
  const [docs, setDocs] = useState([]);
  const [docsTotal, setDocsTotal] = useState(0);
  const [docsLoading, setDocsLoading] = useState(false);

  function handleToolClick(tool) {
    setActiveTool(tool);
    if (tool !== "weather") {
      setWeatherResult(null);
      setError("");
    }
    if (tool !== "mysql") {
      setDbResult(null);
      setDbError("");
    }
    if (tool !== "http") {
      setHttpResult(null);
      setHttpError("");
    }
  }

  async function handleWeatherSearch() {
    if (!city.trim()) return;
    setLoading(true);
    setError("");
    setWeatherResult(null);
    try {
      const res = await queryWeather(city.trim(), days);
      if (res.success) {
        setWeatherResult(res.data);
      } else {
        setError(res.error || "查询失败，请稍后重试");
      }
    } catch (e) {
      setError(e.response?.data?.detail || "网络请求失败，请检查服务是否启动");
    } finally {
      setLoading(false);
    }
  }

  async function handleDatabaseQuery() {
    const sql = dbQuery.trim();
    if (!sql) return;
    setDbLoading(true);
    setDbError("");
    setDbResult(null);
    try {
      const res = await executeDatabaseQuery(sql, dbLimit);
      if (res.success) {
        setDbResult(res);
      } else {
        setDbError(res.error || "查询失败，请检查 SQL 语句");
      }
    } catch (e) {
      setDbError(e.response?.data?.detail || "网络请求失败，请检查服务是否启动");
    } finally {
      setDbLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") handleWeatherSearch();
  }

  function handleDbKeyDown(e) {
    if (e.key === "Enter" && e.shiftKey) return; // Shift+Enter 换行
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleDatabaseQuery();
    }
  }

  async function handleHttpRequest() {
    const url = httpUrl.trim();
    if (!url) return;
    if (!/^https?:\/\/.+/.test(url)) {
      setHttpError("请输入有效的 URL（以 http:// 或 https:// 开头）");
      return;
    }

    setHttpLoading(true);
    setHttpError("");
    setHttpResult(null);

    let headers = {};
    if (httpHeaders.trim()) {
      try {
        headers = JSON.parse(httpHeaders.trim());
        if (typeof headers !== "object" || Array.isArray(headers)) {
          throw new Error("Headers 必须是一个 JSON 对象");
        }
      } catch (e) {
        setHttpError("请求头格式错误，请输入有效的 JSON 对象");
        setHttpLoading(false);
        return;
      }
    }

    try {
      const res = await sendHttpRequest(url, httpMethod, headers, httpBody);
      if (res.success) {
        setHttpResult(res);
      } else {
        setHttpError(res.error || "请求失败，请检查 URL 和参数");
      }
    } catch (e) {
      setHttpError(e.response?.data?.detail || "网络请求失败，请检查服务是否启动");
    } finally {
      setHttpLoading(false);
    }
  }

  function handleHttpKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleHttpRequest();
    }
  }

  // ========== RAG 方法 ==========
  async function fetchDocs() {
    setDocsLoading(true);
    try {
      const data = await listDocs({ page: 1, page_size: 50 });
      setDocs(data.items || []);
      setDocsTotal(data.total || 0);
    } catch {
      setDocs([]);
    }
    setDocsLoading(false);
  }

  function renderWeatherPanel() {
    return (
      <div className="tool-panel">
        <div className="tool-panel-header">
          <span className="tool-panel-title">🌤 天气查询</span>
        </div>
        <div className="weather-search-box">
          <div className="weather-input-group">
            <input
              className="weather-input"
              placeholder="输入城市名称，如 北京、Shanghai、Tokyo"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <select className="weather-days-select" value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={1}>今天</option>
              <option value={2}>今明两天</option>
              <option value={3}>未来三天</option>
            </select>
            <button className="weather-search-btn" onClick={handleWeatherSearch} disabled={loading || !city.trim()}>
              {loading ? <span className="spinner-sm" /> : "查询"}
            </button>
          </div>
        </div>

        {error && <div className="weather-error">{error}</div>}

        {weatherResult && (
          <div className="weather-result">
            <div className="weather-now">
              <div className="weather-city">
                <span className="weather-city-icon">📍</span>
                <span>{weatherResult["城市"]}</span>
              </div>
              <div className="weather-main">
                <div className="weather-temp">{weatherResult["当前温度"]}</div>
                <div className="weather-condition">{weatherResult["天气状况"]}</div>
              </div>
              <div className="weather-details">
                <div className="weather-detail-item">
                  <span className="weather-detail-label">体感温度</span>
                  <span className="weather-detail-value">{weatherResult["体感温度"]}</span>
                </div>
                <div className="weather-detail-item">
                  <span className="weather-detail-label">湿度</span>
                  <span className="weather-detail-value">{weatherResult["湿度"]}</span>
                </div>
                <div className="weather-detail-item">
                  <span className="weather-detail-label">风速</span>
                  <span className="weather-detail-value">{weatherResult["风速"]}</span>
                </div>
                <div className="weather-detail-item">
                  <span className="weather-detail-label">风向</span>
                  <span className="weather-detail-value">{weatherResult["风向"]}</span>
                </div>
                <div className="weather-detail-item">
                  <span className="weather-detail-label">能见度</span>
                  <span className="weather-detail-value">{weatherResult["能见度"]}</span>
                </div>
                <div className="weather-detail-item">
                  <span className="weather-detail-label">紫外线</span>
                  <span className="weather-detail-value">{weatherResult["紫外线指数"]}</span>
                </div>
              </div>
            </div>

            {weatherResult["预报"] && weatherResult["预报"].length > 0 && (
              <div className="weather-forecast">
                <div className="weather-forecast-title">📅 未来预报</div>
                <div className="weather-forecast-grid">
                  {weatherResult["预报"].map((f, i) => (
                    <div key={i} className="weather-forecast-card">
                      <div className="weather-forecast-date">{f["日期"]}</div>
                      <div className="weather-forecast-temps">
                        <span className="weather-forecast-high">{f["最高温"]}</span>
                        <span className="weather-forecast-sep">/</span>
                        <span className="weather-forecast-low">{f["最低温"]}</span>
                      </div>
                      <div className="weather-forecast-avg">{f["平均温"]}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {!weatherResult && !error && (
          <div className="weather-tips">
            <div className="weather-tip-item">💡 支持中文 / 英文城市名</div>
            <div className="weather-tip-item">🌍 覆盖全球主要城市</div>
            <div className="weather-tip-item">📊 可查看未来 1-3 天预报</div>
          </div>
        )}
      </div>
    );
  }

  function renderDatabasePanel() {
    const hasResult = dbResult && dbResult.success;

    return (
      <div className="tool-panel">
        <div className="tool-panel-header">
          <span className="tool-panel-title">🗄 数据库查询</span>
          <span className="tool-panel-hint">仅支持只读操作（SELECT / SHOW / DESCRIBE / EXPLAIN）</span>
        </div>
        <div className="db-query-box">
          <div className="db-query-input-row">
            <textarea
              className="db-query-input"
              placeholder="输入 SQL 查询语句，例如：&#10;SELECT * FROM users LIMIT 10&#10;SHOW TABLES&#10;DESCRIBE users"
              value={dbQuery}
              onChange={(e) => setDbQuery(e.target.value)}
              onKeyDown={handleDbKeyDown}
              rows={4}
            />
          </div>
          <div className="db-query-options">
            <div className="db-limit-group">
              <label className="db-limit-label">行数上限：</label>
              <select className="db-limit-select" value={dbLimit} onChange={(e) => setDbLimit(Number(e.target.value))}>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
              </select>
            </div>
            <button className="db-query-btn" onClick={handleDatabaseQuery} disabled={dbLoading || !dbQuery.trim()}>
              {dbLoading ? <span className="spinner-sm" /> : "▶ 执行查询"}
            </button>
          </div>
        </div>

        {dbError && <div className="db-error">{dbError}</div>}

        {hasResult && (
          <div className="db-result">
            <div className="db-result-meta">
              <span className="db-result-count">📊 返回 {dbResult.row_count} 行</span>
              <span className="db-result-time">⏱ {dbResult.execution_time_ms}ms</span>
              {dbResult.query && (
                <span className="db-result-query">🔍 {dbResult.query}</span>
              )}
            </div>

            {dbResult.columns && dbResult.columns.length > 0 && dbResult.rows && dbResult.rows.length > 0 ? (
              <div className="db-table-wrapper">
                <table className="db-table">
                  <thead>
                    <tr>
                      <th className="db-row-num">#</th>
                      {dbResult.columns.map((col, i) => (
                        <th key={i}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dbResult.rows.map((row, ri) => (
                      <tr key={ri}>
                        <td className="db-row-num">{ri + 1}</td>
                        {row.map((cell, ci) => (
                          <td key={ci}>{cell != null ? String(cell) : <span className="db-null">NULL</span>}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="db-empty">查询成功，但没有返回数据行</div>
            )}
          </div>
        )}

        {!hasResult && !dbError && (
          <div className="db-tips">
            <div className="db-tip-item">💡 仅支持 SELECT / SHOW / DESCRIBE / EXPLAIN 等只读操作</div>
            <div className="db-tip-item">🔒 写操作（INSERT / UPDATE / DELETE / DROP）已被禁止</div>
            <div className="db-tip-item">📏 结果行数上限可自由调整（最多 200 行）</div>
            <div className="db-tip-item">⌨️ 按 Enter 快速执行，Shift+Enter 换行</div>
          </div>
        )}
      </div>
    );
  }

  function renderHttpPanel() {
    const hasResult = httpResult && httpResult.success;
    const methodColors = { 2: "#16a34a", 3: "#ca8a04", 4: "#ea580c", 5: "#dc2626" };
    const statusColor = methodColors[String(httpResult?.status_code)[0]] || "#6b7280";

    return (
      <div className="tool-panel">
        <div className="tool-panel-header">
          <span className="tool-panel-title">🌐 HTTP 请求</span>
        </div>
        <div className="http-request-box">
          <div className="http-input-row">
            <select className="http-method-select" value={httpMethod} onChange={(e) => setHttpMethod(e.target.value)}>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
            <input
              className="http-url-input"
              placeholder="https://api.example.com/data"
              value={httpUrl}
              onChange={(e) => setHttpUrl(e.target.value)}
              onKeyDown={handleHttpKeyDown}
            />
          </div>

          <div className="http-advanced-section">
            <details className="http-details">
              <summary className="http-details-summary">Headers (可选 JSON)</summary>
              <textarea
                className="http-textarea"
                placeholder='{"Content-Type": "application/json", "Authorization": "Bearer token"}'
                value={httpHeaders}
                onChange={(e) => setHttpHeaders(e.target.value)}
                rows={3}
              />
            </details>
          </div>

          {(httpMethod === "POST" || httpMethod === "PUT") && (
            <div className="http-body-section">
              <label className="http-body-label">Request Body</label>
              <textarea
                className="http-textarea"
                placeholder='{"key": "value"}'
                value={httpBody}
                onChange={(e) => setHttpBody(e.target.value)}
                rows={5}
              />
            </div>
          )}

          <div className="http-send-row">
            <button className="http-send-btn" onClick={handleHttpRequest} disabled={httpLoading || !httpUrl.trim()}>
              {httpLoading ? <span className="spinner-sm" /> : "▶ 发送请求"}
            </button>
          </div>
        </div>

        {httpError && <div className="http-error">{httpError}</div>}

        {hasResult && (
          <div className="http-result">
            <div className="http-response-meta">
              <span className="http-status-badge" style={{ backgroundColor: statusColor }}>
                {httpResult.status_code}
              </span>
              <span className="http-method-tag">{httpResult.method}</span>
              <span className="http-url-label">{httpResult.url}</span>
              <span className="http-time-label">⏱ {httpResult.execution_time_ms}ms</span>
            </div>

            <div className="http-response-body">
              <div className="http-response-body-header">Response Body</div>
              <pre className="http-response-pre">
                {httpResult.response != null
                  ? typeof httpResult.response === "object"
                    ? JSON.stringify(httpResult.response, null, 2)
                    : String(httpResult.response)
                  : "(empty)"}
              </pre>
            </div>
          </div>
        )}

        {!hasResult && !httpError && (
          <div className="http-tips">
            <div className="http-tip-item">💡 输入完整 URL（以 http:// 或 https:// 开头）</div>
            <div className="http-tip-item">🌐 支持 GET / POST / PUT / DELETE 方法</div>
            <div className="http-tip-item">📦 POST / PUT 时可填写 JSON 请求体</div>
            <div className="http-tip-item">🔑 可通过 Headers 添加认证信息</div>
            <div className="http-tip-item">⌨️ 按 Enter 快速发送请求</div>
          </div>
        )}
      </div>
    );
  }

  function renderRagPanel() {
    return (
      <div className="tool-panel">
        <div className="tool-panel-header">
          <span className="tool-panel-title">📚 知识库检索</span>
          <span style={{ fontSize: "13px", color: "var(--text-muted)", marginLeft: "auto" }}>
            共 {docsTotal} 篇文档
          </span>
        </div>

        <div style={{ padding: "16px 20px" }}>
          {docsLoading ? (
            <p className="text-muted" style={{ textAlign: "center", padding: "20px" }}>加载中...</p>
          ) : docs.length === 0 ? (
            <p className="text-muted" style={{ textAlign: "center", padding: "20px" }}>暂无文档，请前往「公司知识库」上传</p>
          ) : (
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
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  function renderComingSoon() {
    return (
      <div className="tool-panel">
        <div className="tool-panel-header">
          <span className="tool-panel-title">{TOOLS.find(t => t.tool === activeTool)?.icon} {TOOLS.find(t => t.tool === activeTool)?.label}</span>
        </div>
        <div className="tool-coming-soon">
          <div className="tool-coming-icon">🚧</div>
          <p className="tool-coming-text">该工具正在开发中</p>
          <p className="tool-coming-hint">目前可通过 AI 助手对话使用此功能</p>
        </div>
      </div>
    );
  }

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>🛠 工具中心</h2></div>
        <div className="page-body">
          <div className="tool-grid">
            {TOOLS.map((t) => (
              <div
                key={t.name}
                className={"tool-card" + (activeTool === t.tool ? " active" : "")}
                onClick={() => handleToolClick(t.tool)}
              >
                <div className="tool-card-icon">{t.icon}</div>
                <div className="tool-card-info">
                  <h3>{t.label}</h3>
                  <p>{t.desc}</p>
                </div>
                <span className="tool-status ready">可用</span>
              </div>
            ))}
          </div>

          {activeTool === "weather" && renderWeatherPanel()}
          {activeTool === "mysql" && renderDatabasePanel()}
          {activeTool === "http" && renderHttpPanel()}
          {activeTool === "rag_search" && renderRagPanel()}
          {activeTool && activeTool !== "weather" && activeTool !== "mysql" && activeTool !== "http" && activeTool !== "rag_search" && renderComingSoon()}
          {!activeTool && (
            <div className="tool-welcome">
              <div className="tool-welcome-icon">👆</div>
              <p className="tool-welcome-text">点击上方工具卡片开始使用</p>
            </div>
          )}
        </div>
      </div>
    </AppSidebar>
  );
}
