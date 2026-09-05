import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './HomePage.css'

export default function HomePage() {
  const nav = useNavigate()
  const token = localStorage.getItem('token')
  const username = localStorage.getItem('user')
  const [modal, setModal] = useState(null)

  // 登录守卫：已登录跳转目标页，未登录弹出"请先登录"提示
  const requireLogin = (path, content) => {
    if (token) {
      nav(path)
      return
    }
    setModal({ title: '请先登录', content })
  }

  const handleStartChat = () =>
    requireLogin('/chat', '登录或注册账号后,即可开启与 AI 智能助手的对话。')

  const handleLearnMore = () =>
    requireLogin('/knowledge', '登录或注册账号后,即可查看完整的功能介绍与企业知识库。')

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    nav('/')
  }

  return (
    <div className="home-page">
      {modal && (
        <div className="home-modal-overlay" onClick={() => setModal(null)}>
          <div className="home-modal" onClick={(e) => e.stopPropagation()}>
            <div className="home-modal-title">{modal.title}</div>
            <div className="home-modal-content">{modal.content}</div>
            <div className="home-modal-actions">
              <button
                className="home-modal-btn home-modal-cancel"
                onClick={() => setModal(null)}
              >
                取消
              </button>
              <button
                className="home-modal-btn home-modal-primary"
                onClick={() => {
                  setModal(null)
                  nav('/login?tab=login')
                }}
              >
                去登录
              </button>
            </div>
          </div>
        </div>
      )}

      <nav className="home-navbar">
        <div className="home-brand" onClick={() => nav('/')}>
          <div className="home-logo">E</div>
          <span className="home-brand-text">企业 AI 智能助手</span>
        </div>

        <div className="home-nav-actions">
          {token ? (
            <>
              <span className="home-username">{username || '用户'}</span>
              <button
                className="home-login-btn home-login-btn-danger"
                onClick={handleLogout}
              >
                退出登录
              </button>
            </>
          ) : (
            <>
              <button
                className="home-login-btn"
                onClick={() => nav('/login?tab=login')}
              >
                登录
              </button>
              <button
                className="home-login-btn home-login-btn-primary"
                onClick={() => nav('/login?tab=register')}
              >
                注册
              </button>
            </>
          )}
        </div>
      </nav>

      <main className="home-main">
        <section className="home-hero">
          <span className="home-tag">Enterprise AI · LangGraph</span>
          <h1 className="home-title">
            多 Agent 协作的<br />企业级 AI 助手平台
          </h1>
          <p className="home-subtitle">
            RAG 知识问答 · SQL 数据分析 · 多工具调用。<br />
            为企业打造的下一代 AI 智能助手。
          </p>
          <div className="home-actions">
            <button className="home-btn-primary" onClick={handleStartChat}>
              开始对话
            </button>
            <button className="home-btn-secondary" onClick={handleLearnMore}>
              了解更多
            </button>
          </div>
        </section>

        <section className="home-features">
          <div className="home-feature-card">
            <h3 className="home-feature-title">多智能体编排</h3>
            <p className="home-feature-desc">
              LangGraph Supervisor 路由与多 Worker 协同,自动拆解复杂任务并聚合最终结果。
            </p>
          </div>
          <div className="home-feature-card">
            <h3 className="home-feature-title">RAG 企业知识库</h3>
            <p className="home-feature-desc">
              公司文档语义检索与引用溯源,让每一次回答都有据可依。
            </p>
          </div>
          <div className="home-feature-card">
            <h3 className="home-feature-title">实时工具调用</h3>
            <p className="home-feature-desc">
              内置计算、数据查询与业务分析工具,低延迟响应企业各类问题。
            </p>
          </div>
        </section>
      </main>

      <footer className="home-footer">
        FastAPI · LangGraph · 通义千问 · React
      </footer>
    </div>
  )
}
