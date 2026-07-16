import { useState, useEffect } from "react";
import AppSidebar from "../components/AppSidebar";
import { getProfile, updateProfile, changePassword } from "../api/chat";

export default function ProfilePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profile, setProfile] = useState(null);
  const [emailValue, setEmailValue] = useState("");
  const [savingEmail, setSavingEmail] = useState(false);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    getProfile().then((data) => {
      setProfile(data);
      setEmailValue(data.email || "");
    }).catch(() => {});
  }, []);

  function showMsg(text, type = "success") {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 3000);
  }

  async function handleUpdateEmail() {
    if (!emailValue || !emailValue.includes("@")) {
      showMsg("请输入有效的邮箱地址", "error");
      return;
    }
    setSavingEmail(true);
    try {
      const data = await updateProfile({ email: emailValue });
      setProfile(data);
      showMsg("邮箱修改成功");
    } catch (err) {
      showMsg(err.response?.data?.detail || "邮箱修改失败", "error");
    } finally {
      setSavingEmail(false);
    }
  }

  async function handleChangePassword() {
    if (!oldPw || !newPw) {
      showMsg("请填写原密码和新密码", "error");
      return;
    }
    try {
      await changePassword({ old_password: oldPw, new_password: newPw });
      showMsg("密码修改成功");
      setOldPw("");
      setNewPw("");
    } catch (err) {
      showMsg(err.response?.data?.detail || "密码修改失败", "error");
    }
  }

  return (
    <AppSidebar collapsed={!sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)}>
      <div className="page-layout">
        <div className="page-header"><h2>👤 个人资料</h2></div>
        <div className="page-body">
          {msg && (
            <div className={`toast ${msg.type === "error" ? "toast-error" : ""}`}>
              {msg.text}
            </div>
          )}

          {profile && (
            <div className="section-card" style={{ marginBottom: 20 }}>
              <h3>账号信息</h3>
              <div className="profile-info">
                <div className="profile-row">
                  <span className="profile-label">用户名</span>
                  <span className="profile-value">{profile.username}</span>
                </div>
                <div className="profile-row">
                  <span className="profile-label">用户 ID</span>
                  <span className="profile-value">{profile.id}</span>
                </div>
                <div className="profile-row">
                  <span className="profile-label">邮箱</span>
                  <span className="profile-value">{profile.email || "未设置"}</span>
                </div>
              </div>
            </div>
          )}

          <div className="section-card" style={{ marginBottom: 20 }}>
            <h3>修改邮箱</h3>
            <div className="profile-form" style={{ gap: 12 }}>
              <input
                className="profile-input"
                type="email"
                value={emailValue}
                onChange={(e) => setEmailValue(e.target.value)}
                placeholder="输入新邮箱地址"
              />
              <button className="profile-btn" onClick={handleUpdateEmail} disabled={savingEmail}>
                {savingEmail ? "保存中..." : "保存邮箱"}
              </button>
            </div>
          </div>

          <div className="section-card">
            <h3>修改密码</h3>
            <div className="profile-form" style={{ gap: 12 }}>
              <input
                className="profile-input"
                type="password"
                value={oldPw}
                onChange={(e) => setOldPw(e.target.value)}
                placeholder="原密码"
              />
              <input
                className="profile-input"
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                placeholder="新密码"
              />
              <button className="profile-btn" onClick={handleChangePassword}>修改密码</button>
            </div>
          </div>
        </div>
      </div>
    </AppSidebar>
  );
}
