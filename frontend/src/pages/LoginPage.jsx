import { useState } from "react";
import { login, register } from "../api/chat";

export default function LoginPage() {
  const [mode, setMode] = useState("login"); // login | register
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
        window.location.href = "/";
      } else {
        const data = await login(username, password);
        localStorage.setItem("token", data.token);
        localStorage.setItem("user", data.username);
        window.location.href = "/";
      }
    } catch (err) {
      const d = err.response?.data?.detail;
      const detail = Array.isArray(d) ? d.map(e => e.msg).join("；") : (d || "操作失败，请稍后再试");
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => {
    setMode(mode === "login" ? "register" : "login");
    setError("");
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>企业 AI 智能助手</h1>
        <p className="login-subtitle">Enterprise AI Assistant</p>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <input
              placeholder="用户名"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div className="input-group">
            <input
              type={showPw ? "text" : "password"}
              placeholder="密码"
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

        <button className="demo-btn" onClick={switchMode}>
          {mode === "login" ? "没有账号？去注册" : "已有账号？去登录"}
        </button>
      </div>
    </div>
  );
}
