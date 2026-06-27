import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function ToolCenterPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const tools = [
    { name: "Weather", desc: "查询天气信息", icon: "🌤", status: "ready" },
    { name: "HTTP API", desc: "调用外部 HTTP 接口", icon: "🌐", status: "ready" },
    { name: "Database", desc: "查询 MySQL 数据库", icon: "🗄", status: "ready" },
  ];
  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>🛠 Tool Center</h2></div>
        <div className="page-body">
          <div className="tool-grid">
            {tools.map((t) => (
              <div key={t.name} className="tool-card">
                <div className="tool-card-icon">{t.icon}</div>
                <div className="tool-card-info">
                  <h3>{t.name}</h3>
                  <p>{t.desc}</p>
                </div>
                <span className={`tool-status ${t.status}`}>{t.status === "ready" ? "可用" : t.status}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppSidebar>
  );
}
