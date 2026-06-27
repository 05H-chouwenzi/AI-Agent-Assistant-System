import { useState } from "react";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import AppSidebar from "../components/AppSidebar";
import { useChat } from "../hooks/useChat";

const FEATURES = [
  { icon: "📚", label: "企业知识检索", desc: "基于 RAG 检索内部文档" },
  { icon: "🌤", label: "天气查询", desc: "调用实时天气工具" },
  { icon: "🛠", label: "Tool Calling", desc: "动态工具调用" },
  { icon: "📄", label: "PDF 问答", desc: "上传文档智能问答" },
  { icon: "🤖", label: "LangGraph Workflow", desc: "Agent 工作流引擎" },
];

const SUGGESTIONS = [
  "公司请假流程怎么走？",
  "查看最近的天气情况",
  "企业有哪些福利制度？",
  "如何申请报销？",
];

export default function ChatPage() {
  const { messages, loading, send, bottomRef,
    conversations, activeId, setActiveId,
    newChat, deleteConversation, clearMessages } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="chat-main">
        <div className="chat-header">
          <div className="chat-header-left">
            <h2>AI Assistant</h2>
            <span className="header-model-badge">qwen-plus</span>
          </div>
          <button className="header-clear-btn" onClick={clearMessages}>清空对话</button>
        </div>

        <div className="chat-messages">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">✦</div>
              <h3>欢迎使用 Enterprise AI Assistant</h3>
              <p className="welcome-sub">不只是聊天机器人 — 企业级 AI Agent 工作平台</p>
              <div className="features-grid">
                {FEATURES.map((f, i) => (
                  <div key={i} className="feature-item">
                    <span className="feature-icon">{f.icon}</span>
                    <div>
                      <strong>{f.label}</strong>
                      <p>{f.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="suggestions">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} className="suggestion-chip" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
          )}
          {loading && (
            <div className="message message-ai">
              <div className="message-avatar">✦</div>
              <div className="message-content">
                <div className="message-bubble typing">
                  <span className="dot" /><span className="dot" /><span className="dot" />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <ChatInput onSend={send} loading={loading} />
      </div>
    </AppSidebar>
  );
}
