import { Activity, Menu } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import styles from './Topbar.module.css'

export default function Topbar({ onMenu, user, mode }) {
  const navigate = useNavigate()
  const isHome = mode === 'home'
  const description = isHome
    ? '모의투자와 실전투자의 핵심 상태를 한눈에 확인하세요.'
    : `${mode === 'simulated' ? '가상 자금 운용' : 'Upbit 실제 자산 운용'} 현황입니다.`

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <button className={styles.menu} onClick={onMenu} aria-label="사이드바 열기"><Menu size={20} /></button>
        <div className={styles.pageInfo}>
          <div className={styles.titleRow}>
            <button className={styles.brandLink} onClick={() => navigate('/dashboard')} aria-label="SignalTrade 홈으로 이동">
              <span><Activity size={17} /></span>
              <strong>SignalTrade</strong>
            </button>
            {!isHome && <span className={mode === 'simulated' ? styles.paperMode : styles.liveMode}>{mode === 'simulated' ? '모의투자' : '실전투자'}</span>}
          </div>
          <p>안녕하세요, {user?.nickname || ''}님. {description}</p>
        </div>
      </div>

      <div className={styles.actions}>
        <div className={styles.profile}>
          <div>{user?.nickname?.slice(0, 2) || '-'}</div>
          <span><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></span>
        </div>
      </div>
    </header>
  )
}
