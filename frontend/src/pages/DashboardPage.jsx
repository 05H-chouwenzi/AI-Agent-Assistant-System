import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header">
          <h2>📊 Dashboard</h2>
        </div>
        <div className="dashboard-grid">
          <div className="stat-card">
            <div className="stat-icon">💬</div>
            <div className="stat-info">
              <span className="stat-value">12</span>
              <span className="stat-label">今日调用</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📚</div>
            <div className="stat-info">
              <span className="stat-value">5</span>
              <span className="stat-label">知识库文档</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🛠</div>
            <div className="stat-info">
              <span className="stat-value">3</span>
              <span className="stat-label">工具</span>
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🔄</div>
            <div className="stat-info">
              <span className="stat-value">48</span>
              <span className="stat-label">Workflow 执行</span>
            </div>
          </div>
        </div>
        <div className="dashboard-section">
          <h3>最近聊天</h3>
          <p className="text-muted" style={{textAlign:"center",padding:"24px"}}>暂无数据</p>
        </div>
      </div>
    </AppSidebar>
  );
}
