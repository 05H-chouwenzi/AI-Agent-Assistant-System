import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { login, register } from "../api/chat";
import "./LoginPage.css";

export default function LoginPage() {
  const nav = useNavigate();
  const location = useLocation();
  const [mode, setMode] = useState(() => {
    const params = new URLSearchParams(location.search);
    return params.get("tab") === "register" ? "register" : "login";
  }); // login | register
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const switchMode = (m) => {
    setMode(m);
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError("请输入用户名和密码");
      return;
    }
    setError("");
    setLoading(true);
    try {
      if (mode === "register") {
        await register(username, password);
        const data = await login(username, password);
        localStorage.setItem("token", data.token);
        localStorage.setItem("user", data.username);
        nav("/");
      } else {
        const data = await login(username, password);
        localStorage.setItem("token", data.token);
        localStorage.setItem("user", data.username);
        nav("/");
      }
    } catch (err) {
      const data = err.response?.data;
      const msg = data?.detail || data?.message || err.message || "操作失败，请稍后再试";
      const detail = Array.isArray(msg) ? msg.map(e => e.msg).join("；") : msg;
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-panels">
        <div className="login-info-card">
          <div className="login-info-title">测试账号</div>
          <div className="login-info-row">
            <span className="login-info-label">账号</span>
            <span className="login-info-value">admin</span>
          </div>
          <div className="login-info-row">
            <span className="login-info-label">密码</span>
            <span className="login-info-value">admin123</span>
          </div>
        </div>

        <div className="login-card">
        <h1 className="login-title">企业 AI 智能助手</h1>
        <p className="login-subtitle">Enterprise AI Assistant</p>

        <div className="login-tabs">
          <button
            className={"login-tab" + (mode === "login" ? " active" : "")}
            onClick={() => switchMode("login")}
          >
            登录
          </button>
          <button
            className={"login-tab" + (mode === "register" ? " active" : "")}
            onClick={() => switchMode("register")}
          >
            注册
          </button>
        </div>

        <form onSubmit={handleSubmit} autoComplete="off">
          <div className="input-group">
            <input
              placeholder="用户名"
              autoComplete="off"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div className="input-group">
            <input
              type={showPw ? "text" : "password"}
              placeholder="密码"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="button" className="pw-toggle" onClick={() => setShowPw(!showPw)}>
              {showPw ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </svg>
              )}
            </button>
          </div>
          {error && <p className="login-error">{error}</p>}
          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "处理中..." : mode === "login" ? "登 录" : "注 册"}
          </button>
        </form>
        </div>
      </div>
    </div>
  );
}
