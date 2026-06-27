import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Sidebar({ conversations, onNewChat, activeId, onSelect, onDelete, collapsed }) {
  const navigate = useNavigate();
  const user = localStorage.getItem("user") || "未登录";
  const [showLogout, setShowLogout] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  };

  return (
    <div className={`sidebar${collapsed ? " collapsed" : ""}`}>
        <div className="sidebar-header">
          <span className="sidebar-logo">Enterprise AI</span>
        </div>

        <button className="new-chat-btn" onClick={onNewChat}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新对话
        </button>

        <div className="sidebar-section-title">聊天记录</div>
        <div className="conversation-list">
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conv-item${conv.id === activeId ? " active" : ""}`}
              onClick={() => onSelect(conv.id)}
            >
              <span className="conv-title">{conv.title}</span>
              <button
                className="conv-delete"
                onClick={(e) => {
                  e.stopPropagation();
                  if (conversations.length <= 1) return;
                  onDelete(conv.id);
                }}
                title="删除对话"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-user" onClick={() => setShowLogout(!showLogout)}>
            <div className="user-avatar">👤</div>
            <span>{user}</span>
            <svg className="user-arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>

          {showLogout && (
            <button className="sidebar-logout-btn" onClick={handleLogout}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              退出登录
            </button>
          )}
        </div>
    </div>
  );
}
