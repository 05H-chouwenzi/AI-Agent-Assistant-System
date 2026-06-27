import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function LogsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>📜 Logs</h2></div>
        <div className="page-body">
          <div className="section-card"><h3>系统日志</h3><p className="text-muted" style={{textAlign:"center",padding:"24px"}}>暂无日志</p></div>
        </div>
      </div>
    </AppSidebar>
  );
}
