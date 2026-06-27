import { useState } from "react";
import AppSidebar from "../components/AppSidebar";

export default function WorkflowPage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>🔄 Workflow</h2></div>
        <div className="page-body">
          <div className="workflow-visual">
            <div className="wf-node start">START</div>
            <div className="wf-arrow">↓</div>
            <div className="wf-node planner">Planner</div>
            <div className="wf-arrow">↓</div>
            <div className="wf-node-row">
              <div className="wf-node rag">RAG</div>
              <div className="wf-node tool">Tool</div>
              <div className="wf-node direct">Direct LLM</div>
            </div>
            <div className="wf-arrow">↓</div>
            <div className="wf-node llm">LLM</div>
            <div className="wf-arrow">↓</div>
            <div className="wf-node response">Response</div>
            <div className="wf-arrow">↓</div>
            <div className="wf-node end">END</div>
          </div>
        </div>
      </div>
    </AppSidebar>
  );
}
