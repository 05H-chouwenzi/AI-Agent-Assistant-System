import { useState, useEffect } from "react";
import AppSidebar from "../components/AppSidebar";
import { getProfile, changePassword } from "../api/chat";

export default function ProfilePage() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [profile, setProfile] = useState(null);
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    getProfile().then((data) => {
      setProfile(data);
    }).catch(() => {});
  }, []);

  function showMsg(text, type = "success") {
    setMsg({ text, type });
    setTimeout(() => setMsg(null), 3000);
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
              </div>
            </div>
          )}

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
