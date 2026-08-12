import { useEffect, useRef, useState } from 'react'
import { Activity, BarChart3, CheckCircle2, Loader2, ChevronDown, CircleUserRound, LogOut, Menu, Settings, TriangleAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { clearToken } from '../../api/client'
import styles from './Topbar.module.css'

export default function Topbar({ onMenu, user, mode, title, subtitle, readiness = [] }) {
  const navigate = useNavigate()
  const [profileOpen, setProfileOpen] = useState(false)
  const profileRef = useRef(null)
  const isHome = mode === 'home'
  const readyCount = readiness.filter((item) => item.ready === true).length
  // 아직 확인 중인 항목이 있으면 개수 대신 확인 중으로 표시합니다.
  const checking = readiness.some((item) => item.ready === null)
  const description = isHome
    ? '모의투자와 실전투자의 핵심 상태를 한눈에 확인하세요.'
    : `${mode === 'simulated' ? '가상 자금 운용' : 'Upbit 실제 자산 운용'} 현황입니다.`

  useEffect(() => {
    const closeOnOutside = (event) => {
      if (!profileRef.current?.contains(event.target)) setProfileOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setProfileOpen(false)
    }
    document.addEventListener('mousedown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  const moveFromProfile = (path) => {
    setProfileOpen(false)
    navigate(path)
  }

  const handleLogout = () => {
    setProfileOpen(false)
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <button className={styles.menu} onClick={onMenu} aria-label="사이드바 열기"><Menu size={20} /></button>
        <div className={styles.pageInfo}>
          {title ? <div className={styles.titleRow}><strong>{title}</strong></div> : <div className={styles.titleRow}>
              <button className={styles.brandLink} onClick={() => navigate('/dashboard')} aria-label="SignalTrade 홈으로 이동">
                <span><Activity size={17} /></span>
                <strong>SignalTrade</strong>
              </button>
              {!isHome && mode && <span className={mode === 'simulated' ? styles.paperMode : styles.liveMode}>{mode === 'simulated' ? '모의투자' : '실전투자'}</span>}
            </div>}
          <p>{subtitle || `안녕하세요, ${user?.nickname || ''}님. ${description}`}</p>
        </div>
      </div>

      <div className={styles.actions}>
        {readiness.length > 0 && (
          <div className={styles.readiness} aria-label={`외부 서비스 설정 ${readyCount}/${readiness.length}`}>
            <span className={styles.readinessTitle}>
              <small>외부 서비스 설정</small>
              <strong>{checking ? '확인 중' : `${readyCount}/${readiness.length} 설정됨`}</strong>
            </span>
            <div className={styles.readinessItems}>
              {readiness.map((item) => (
                <span
                  key={item.label}
                  className={item.ready === null ? styles.checking : item.ready ? styles.ready : styles.notReady}
                  title={`${item.label}: ${item.detail}`}
                >
                  {item.ready === null ? <Loader2 size={14} /> : item.ready ? <CheckCircle2 size={14} /> : <TriangleAlert size={14} />}
                  <b>{item.label}</b>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className={styles.profileMenu} ref={profileRef}>
          <button
            className={styles.profile}
            onClick={() => setProfileOpen((open) => !open)}
            aria-haspopup="menu"
            aria-expanded={profileOpen}
          >
            <span className={styles.avatar}><CircleUserRound size={22} /></span>
            <span className={styles.profileText}><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></span>
            <ChevronDown className={profileOpen ? styles.chevronOpen : ''} size={16} />
          </button>

          {profileOpen && (
            <div className={styles.dropdown} role="menu">
              <div className={styles.dropdownUser}>
                <CircleUserRound size={24} />
                <span><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></span>
              </div>
              <button role="menuitem" onClick={() => moveFromProfile('/analytics')}>
                <BarChart3 size={17} />
                <span><strong>사용자 분석</strong><small>투자 성과 확인</small></span>
              </button>
              <button role="menuitem" onClick={() => moveFromProfile('/settings')}>
                <Settings size={17} />
                <span><strong>계정 설정</strong><small>회원정보 및 API 관리</small></span>
              </button>
            </div>
          )}
        </div>

        <button className={styles.logoutButton} onClick={handleLogout}>
          <LogOut size={16} />
          로그아웃
        </button>
      </div>
    </header>
  )
}
