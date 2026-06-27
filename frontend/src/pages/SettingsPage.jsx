import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function SettingsPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>⚙ Settings</h2></div>
        <div className="page-body">
          <div className="section-card">
            <h3>LLM 配置</h3>
            <div className="setting-row"><span>模型</span><span className="setting-value">qwen-plus</span></div>
            <div className="setting-row"><span>Base URL</span><span className="setting-value">https://dashscope.aliyuncs.com/compatible-mode/v1</span></div>
          </div>
          <div className="section-card" style={{marginTop:"16px"}}>
            <h3>RAG 配置</h3>
            <div className="setting-row"><span>Chunk Size</span><span className="setting-value">500</span></div>
            <div className="setting-row"><span>Chunk Overlap</span><span className="setting-value">50</span></div>
            <div className="setting-row"><span>Top-K</span><span className="setting-value">3</span></div>
          </div>
        </div>
      </div>
    </AppSidebar>
  );
}
