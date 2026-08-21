import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import styles from './SiteHeader.module.css'

export default function SiteHeader({ user, readiness = [], onLogout }) {
  const navigate = useNavigate()
  const location = useLocation()
  const headerRef = useRef(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [investmentOpen, setInvestmentOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)

  const readyCount = readiness.filter((item) => item.ready === true).length
  const checking = readiness.some((item) => item.ready === null)

  useEffect(() => {
    const closeOnOutside = (event) => {
      if (!headerRef.current?.contains(event.target)) {
        setInvestmentOpen(false)
        setAccountOpen(false)
        setMobileOpen(false)
      }
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') {
        setInvestmentOpen(false)
        setAccountOpen(false)
        setMobileOpen(false)
      }
    }
    document.addEventListener('mousedown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('mousedown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [])

  const move = (path) => {
    navigate(path)
    setInvestmentOpen(false)
    setAccountOpen(false)
    setMobileOpen(false)
  }

  const active = (path) => location.pathname === path
  const investmentActive = location.pathname.startsWith('/dashboard/')

  return (
    <header className={styles.header} ref={headerRef}>
      <div className={styles.inner}>
        <button className={styles.brand} onClick={() => move('/dashboard')} aria-label="SignalTrade 홈으로 이동">
          <strong>Signal</strong><span>Trade</span>
        </button>

        <button
          className={styles.mobileToggle}
          onClick={() => setMobileOpen((open) => !open)}
          aria-label="주 메뉴 열기"
          aria-expanded={mobileOpen}
        >
          <i /><i /><i />
        </button>

        <nav className={`${styles.nav} ${mobileOpen ? styles.navOpen : ''}`} aria-label="주 메뉴">
          <button className={active('/dashboard') ? styles.active : ''} onClick={() => move('/dashboard')}>
            대시보드
          </button>

          <div className={`${styles.navDropdown} ${investmentActive ? styles.activeGroup : ''}`}>
            <button
              onClick={() => setInvestmentOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={investmentOpen}
            >
              투자 관리 <span className={styles.chevron}>⌄</span>
            </button>
            <div className={`${styles.investmentMenu} ${investmentOpen ? styles.dropdownOpen : ''}`} role="menu">
              <button role="menuitem" onClick={() => move('/dashboard/simulated')}>
                <strong>모의투자</strong>
                <small>가상 자금으로 전략 검증</small>
              </button>
              <button role="menuitem" onClick={() => move('/dashboard/live')}>
                <strong>실전투자</strong>
                <small>Upbit 실제 계좌 운용</small>
              </button>
            </div>
          </div>

          <button className={active('/analytics') ? styles.active : ''} onClick={() => move('/analytics')}>
            사용자 분석
          </button>
          <button className={location.pathname.startsWith('/guide') ? styles.active : ''} onClick={() => move('/guide')}>
            이용 가이드
          </button>
        </nav>

        <div className={styles.actions}>
          {readiness.length > 0 && (
            <span className={styles.readiness}>
              <i className={checking ? styles.checking : readyCount === readiness.length ? styles.ready : styles.attention} />
              {checking ? '연결 확인 중' : `서비스 연결 ${readyCount}/${readiness.length}`}
            </span>
          )}

          <div className={styles.account}>
            <button
              className={styles.accountButton}
              onClick={() => setAccountOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={accountOpen}
            >
              {user?.nickname || user?.username || '사용자'} <span className={styles.chevron}>⌄</span>
            </button>
            {accountOpen && (
              <div className={styles.accountMenu} role="menu">
                <div><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></div>
                <button role="menuitem" onClick={() => move('/settings')}>계정 설정</button>
                <button className={styles.logout} role="menuitem" onClick={onLogout}>로그아웃</button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
