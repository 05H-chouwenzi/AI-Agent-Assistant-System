import { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import AppSidebar from "../components/AppSidebar";
import { useChat } from "../hooks/useChat";

const QUICK_ACTIONS = [
  {
    label: "企业知识检索",
    desc: "检索内部文档知识库，开启 RAG 问答",
    action: "navigate",
    target: "/knowledge",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        <path d="M12 6v7" /><path d="M9 9l3-3 3 3" />
      </svg>
    ),
  },
  {
    label: "天气查询",
    desc: "跳转至工具中心查询实时天气",
    action: "navigate",
    target: "/tools?tool=weather",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
      </svg>
    ),
  },
  {
    label: "Tool Calling",
    desc: "查看可用工具列表并进行测试调用",
    action: "navigate",
    target: "/tools",
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
      </svg>
    ),
  },
  {
    label: "PDF 问答",
    desc: "上传 PDF 文档，针对文档内容进行智能问答",
    action: "upload",
    target: null,
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
];

export default function ChatPage() {
  const { messages, loading, thinkingStatus, send, bottomRef,
    conversations, activeId, setActiveId,
    newChat, deleteConversation, clearMessages } = useChat();

  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [searchParams] = useSearchParams();
  const fileInputRef = useRef(null);

  // 消息更新时自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const convId = searchParams.get("conv");
    if (convId) {
      const id = parseInt(convId);
      if (id && id !== activeId) {
        setActiveId(id);
      }
    }
  }, [searchParams]);

  function handleAction(action) {
    if (action.action === "navigate") {
      navigate(action.target);
    } else if (action.action === "send") {
      send(action.target);
    } else if (action.action === "upload") {
      fileInputRef.current?.click();
    }
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (file) {
      send(`请帮我分析上传的 PDF 文件：${file.name}`);
      e.target.value = "";
    }
  }

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
              <div className="welcome-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <h3>AI 工作台</h3>
              <p className="welcome-sub">选择一个快捷操作，或直接在下方输入问题开始对话</p>
              <div className="workbench-grid">
                {QUICK_ACTIONS.map((action, i) => (
                  <div key={i} className="workbench-card" onClick={() => handleAction(action)} role="button" tabIndex={0}>
                    <div className="workbench-icon">{action.icon}</div>
                    <div className="workbench-info">
                      <strong>{action.label}</strong>
                      <p>{action.desc}</p>
                    </div>
                    <span className="workbench-arrow">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                      </svg>
                    </span>
                  </div>
                ))}
              </div>
              <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleFileChange} style={{ display: "none" }} />
            </div>
          ) : (
            messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
          )}
          {loading && (
            <div className="message message-ai">
              <div className="message-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <div className="message-content">
                <div className="message-bubble">
                  <div className="thinking-status">
                    <span className="thinking-dots">
                      <span className="dot" /><span className="dot" /><span className="dot" />
                    </span>
                    {thinkingStatus && (
                      <span className="thinking-text">{thinkingStatus}</span>
                    )}
                  </div>
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
