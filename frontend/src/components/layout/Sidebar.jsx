import { Activity, BarChart3, CircleUserRound, FlaskConical, LayoutDashboard, LogOut, Settings, ShieldAlert, X } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import styles from './Sidebar.module.css'

export default function Sidebar({ open, onClose, user, onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const move = (path) => {
    navigate(path)
    onClose()
  }

  return (
    <>
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`}>
        <div className={styles.top}>
          <button className={styles.brand} onClick={() => move('/dashboard')} aria-label="SignalTrade 홈으로 이동">
            <span><Activity size={22} /></span>
            <b>SignalTrade</b>
          </button>
          <button className={styles.close} onClick={onClose} aria-label="사이드바 닫기"><X size={20} /></button>
        </div>

        <nav className={styles.nav}>
          <section>
            <h4>OVERVIEW</h4>
            <button className={location.pathname === '/dashboard' ? styles.active : ''} onClick={() => move('/dashboard')}>
              <LayoutDashboard size={18} />
              <span>홈</span>
            </button>
          </section>
          <section>
            <h4>INVESTMENT</h4>
            <button className={location.pathname === '/dashboard/simulated' ? styles.active : ''} onClick={() => move('/dashboard/simulated')}>
              <FlaskConical size={18} />
              <span>모의투자</span>
            </button>
            <button className={location.pathname === '/dashboard/live' ? styles.active : ''} onClick={() => move('/dashboard/live')}>
              <ShieldAlert size={18} />
              <span>실전투자</span>
            </button>
          </section>
          <section>
            <h4>ACCOUNT</h4>
            <button className={location.pathname === '/analytics' ? styles.active : ''} onClick={() => move('/analytics')}>
              <BarChart3 size={18} />
              <span>사용자 분석</span>
            </button>
            <button className={location.pathname === '/settings' ? styles.active : ''} onClick={() => move('/settings')}>
              <Settings size={18} />
              <span>계정 설정</span>
            </button>
          </section>
        </nav>

        <div className={styles.footer}>
          <div className={styles.profile}>
            <CircleUserRound size={28} />
            <span><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></span>
          </div>
          <button className={styles.logout} onClick={onLogout}>
            <LogOut size={16} /> 로그아웃
          </button>
        </div>
      </aside>
      {open && <button className={styles.overlay} onClick={onClose} aria-label="사이드바 닫기" />}
    </>
  )
}
