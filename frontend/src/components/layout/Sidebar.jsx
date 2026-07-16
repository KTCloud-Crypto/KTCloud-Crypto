import { Activity, CircleUserRound, LayoutDashboard, LogOut, X } from 'lucide-react'
import styles from './Sidebar.module.css'

export default function Sidebar({ open, onClose, user, onLogout }) {
  return (
    <>
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`}>
        <div className={styles.top}>
          <div className={styles.brand}>
            <span><Activity size={22} /></span>
            <b>AutoTrade</b>
          </div>
          <button className={styles.close} onClick={onClose} aria-label="사이드바 닫기"><X size={20} /></button>
        </div>

        <nav className={styles.nav}>
          <section>
            <button className={styles.active}>
              <LayoutDashboard size={18} />
              <span>대시보드</span>
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
