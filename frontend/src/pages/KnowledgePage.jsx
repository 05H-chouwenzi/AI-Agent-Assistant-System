import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function KnowledgePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>📚 Knowledge Base</h2></div>
        <div className="page-body">
          <div className="upload-area">
            <div className="upload-icon">📄</div>
            <p>拖拽文件到此处上传，或点击选择文件</p>
            <p className="text-muted" style={{fontSize:"13px",marginTop:"8px"}}>支持 PDF · Word · Markdown · TXT</p>
            <button className="upload-btn">选择文件</button>
          </div>
          <div className="section-card" style={{marginTop:"24px"}}>
            <h3>已上传文档</h3>
            <p className="text-muted" style={{textAlign:"center",padding:"24px"}}>暂无文档</p>
          </div>
        </div>
      </div>
    </AppSidebar>
  );
}
