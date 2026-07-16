import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getConversations, createConversation, deleteConversation } from "../api/chat";
import ConfirmDialog from "./ConfirmDialog";
import { useChat } from "../contexts/ChatContext";

const NAV_ITEMS = [
  { path: "/dashboard", label: "仪表盘", icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  )},
  { path: "/knowledge", label: "公司知识库", icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      <path d="M12 6v7" /><path d="M9 9l3-3 3 3" />
    </svg>
  )},
  { path: "/tools", label: "工具中心", icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  )},
  { path: "/logs", label: "日志", icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  )},
  { path: "/chat", label: "AI 助手", icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )},
];

export default function AppSidebar({ collapsed, onToggle, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = localStorage.getItem("user") || "未登录";
  const [chatPop, setChatPop] = useState(false);
  const [convs, setConvs] = useState([]);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const chatNavRef = useRef();
  const { isThinking, thinkingStatus } = useChat();

  useEffect(() => {
    function handleClick(e) {
      if (chatNavRef.current && !chatNavRef.current.contains(e.target)) {
        setChatPop(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  async function fetchConvs() {
    try { const d = await getConversations(); setConvs(d); } catch { setConvs([]); }
  }
  function handleChatToggle() {
    setChatPop(p => {
      const next = !p;
      if (next) fetchConvs();
      return next;
    });
  }

  async function handleNewChat() {
    try { const conv = await createConversation("新对话"); setConvs(p => [conv, ...p]); navigate("/chat?conv=" + conv.id); }
    catch (e) { console.error(e); }
  }

  function selectConversation(id) { setChatPop(false); navigate("/chat?conv=" + id); }
  function handleDeleteClick(e, id) { e.stopPropagation(); setConfirmDeleteId(id); }

  async function handleConfirmDelete() {
    if (confirmDeleteId == null) return;
    try { await deleteConversation(confirmDeleteId); setConvs(p => p.filter(c => c.id !== confirmDeleteId)); }
    catch (e) { console.error(e); }
    setConfirmDeleteId(null);
  }
  function handleCancelDelete() { setConfirmDeleteId(null); }

  const handleLogout = () => { localStorage.removeItem("token"); localStorage.removeItem("user"); navigate("/login"); };
  const isChat = location.pathname === "/chat";

  return (
    <div className="app-layout">
      <div className={"app-sidebar" + (collapsed ? " collapsed" : "")}>
        <div className="app-sidebar-header">
          <span className="app-sidebar-logo">✦Enterprise AI</span>
          <button className="sidebar-toggle" onClick={onToggle}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>
        <nav className="app-nav">
          {NAV_ITEMS.map((item) =>
            item.path === "/chat" ? (
              <div key={item.path} style={{ position: "relative" }} ref={chatNavRef}>
                <div className={"nav-item" + (location.pathname.startsWith("/chat") ? " active" : "")} onClick={() => { setChatPop(false); navigate("/chat"); }}>
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label nav-chat-label">{item.label}</span>
                  {isThinking && <span className="nav-thinking-badge" title={thinkingStatus}>●</span>}
                  <span className="nav-btn-group">
                    <span className="nav-add-btn" onClick={(e) => { e.stopPropagation(); handleNewChat(); }} title="新建对话">+</span>
                    <span className="nav-popover-btn" onClick={(e) => { e.stopPropagation(); handleChatToggle(); }} title="切换对话">▾</span>
                  </span>
                </div>
                <div className={"chat-popover" + (chatPop ? " open" : "")}>
                  {convs.length === 0 ? (
                    <div className="chat-popover-empty">暂无语录</div>
                  ) : (
                    <div className="chat-popover-list">
                      {convs.map((c) => (
                        <div key={c.id} className="chat-popover-item" onClick={() => selectConversation(c.id)}>
                          <span className="chat-popover-title">{c.title}</span>
                          <button className="chat-popover-delete" onClick={(e) => handleDeleteClick(e, c.id)} title="删除对话">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                      ))}
                      {confirmDeleteId != null && (
                        <ConfirmDialog open={true} title="删除对话" message="删除后将无法恢复，确定要删除该对话吗？" onCancel={handleCancelDelete} onConfirm={handleConfirmDelete} />
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div key={item.path} className={"nav-item" + (location.pathname === item.path ? " active" : "")} onClick={() => navigate(item.path)}>
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
              </div>
            )
          )}
        </nav>
        <div className="app-sidebar-footer">
          <div className="sidebar-logout-group">
            <button className="sidebar-logout-btn" onClick={() => navigate("/settings")}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
              <span>设置</span>
            </button>
            <button className="sidebar-logout-btn" onClick={handleLogout}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              <span>退出登录</span>
            </button>
          </div>
          <div className="sidebar-user" onClick={() => navigate("/profile")}>
            <div className="user-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a0a0a0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <span>{user}</span>

          </div>
        </div>
      </div>
      <div className={"app-content" + (isChat ? " chat-content" : "")}>{children}</div>
      {!isChat && isThinking && (
        <div className="global-thinking-bar" onClick={() => navigate("/chat")} title="点击回到 AI 助手查看回复">
          <span className="global-thinking-dots">
            <span className="dot" /><span className="dot" /><span className="dot" />
          </span>
          <span className="global-thinking-text">{thinkingStatus || "🤖 AI 正在思考中..."}</span>
          <span className="global-thinking-hint">点击查看 →</span>
        </div>
      )}
    </div>
  );
}
