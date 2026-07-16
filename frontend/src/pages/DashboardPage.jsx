import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import BalancePanel from '../components/dashboard/BalancePanel'
import PositionsPanel from '../components/dashboard/PositionsPanel'
import TradesPanel from '../components/dashboard/TradesPanel'
import WebhookPanel from '../components/dashboard/WebhookPanel'
import { apiFetch, clearToken } from '../api/client'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/users/me')
      .then(setUser)
      .catch((err) => setError(err.message))
  }, [])

  const handleLogout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className={styles.app}>
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        onLogout={handleLogout}
      />

      <main className={styles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} user={user} />

        <section className={styles.content}>
          <div className={styles.heading}>
            <div><h2>계정 요약</h2><p>{user ? `@${user.username}` : ''}</p></div>
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <BalancePanel />
          <PositionsPanel />
          <TradesPanel />
          <WebhookPanel user={user} onUserChange={setUser} />
        </section>

        <footer className={styles.footer}>
          <span>© 2026 AutoTrade. All rights reserved.</span>
        </footer>
      </main>
    </div>
  )
}
