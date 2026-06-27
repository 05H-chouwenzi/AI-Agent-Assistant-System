import { useLocation, useNavigate } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/dashboard", label: "仪表盘", icon: "📊" },
  { path: "/chat", label: "AI 助手", icon: "💬" },
  { path: "/knowledge", label: "知识库", icon: "📚" },
  { path: "/tools", label: "工具中心", icon: "🛠" },
  { path: "/workflow", label: "工作流", icon: "🔄" },
  { path: "/logs", label: "日志", icon: "📜" },
  { path: "/settings", label: "设置", icon: "⚙" },
];

export default function AppSidebar({ collapsed, onToggle, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const user = localStorage.getItem("user") || "未登录";

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    navigate("/login");
  };

  const isChat = location.pathname === "/";

  return (
    <div className="app-layout">
      <div className={`app-sidebar${collapsed ? " collapsed" : ""}`}>
        <div className="app-sidebar-header">
          <span className="app-sidebar-logo">✦ Enterprise AI</span>
          <button className="sidebar-toggle" onClick={onToggle}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>

        <nav className="app-nav">
          {NAV_ITEMS.map((item) => (
            <div
              key={item.path}
              className={`nav-item${location.pathname === item.path ? " active" : ""}`}
              onClick={() => navigate(item.path)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </div>
          ))}
        </nav>

        <div className="app-sidebar-footer">
          <div className="sidebar-logout-group">
            <button className="sidebar-logout-btn" onClick={handleLogout}>退出登录</button>
          </div>
          <div className="sidebar-user">
            <div className="user-avatar">👤</div>
            <span>{user}</span>
          </div>
        </div>
      </div>

      <div className={`app-content${isChat ? " chat-content" : ""}`}>
        {children}
      </div>
    </div>
  );
}
