import MarketTicker from '../components/dashboard/MarketTicker'
import { serviceReadiness } from '../utils/serviceReadiness'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import BalancePanel from '../components/dashboard/BalancePanel'
import PortfolioPanel from '../components/dashboard/PortfolioPanel'
import StrategyPanel from '../components/dashboard/StrategyPanel'
import ActivityPanel from '../components/dashboard/ActivityPanel'
import PaperAccountPanel from '../components/dashboard/PaperAccountPanel'
import { apiFetch, clearToken } from '../api/client'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { mode } = useParams()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!['simulated', 'live'].includes(mode)) {
      navigate('/dashboard', { replace: true })
      return
    }
    let active = true
    const loadUser = () => {
      apiFetch('/users/me')
        .then(async (currentUser) => {
          if (!active) return
          if (mode === 'live' && !currentUser.has_api_key) {
            setUser(currentUser)
            setError('')
            return
          }
          setError('')
          if (currentUser.execution_mode !== mode) {
            setUser(await apiFetch('/users/me', {
              method: 'PUT',
              body: JSON.stringify({ execution_mode: mode }),
            }))
          } else {
            setUser(currentUser)
          }
        })
        .catch((err) => setError(err.message))
    }
    loadUser()
    // 다른 화면에서 API 키를 등록·삭제해도 상단바 상태가 따라오도록 주기적으로 갱신합니다.
    const timer = window.setInterval(loadUser, 10_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [mode, navigate])

  const handleLogout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  const liveBlocked = mode === 'live' && user && !user.has_api_key
  const liveAccessPending = mode === 'live' && !user

  return (
    <div className={styles.app}>
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        user={user}
        mode={mode}
        onLogout={handleLogout}
      />

      <main className={styles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} user={user} mode={mode} readiness={serviceReadiness(user)} />

        <section className={styles.content}>
          <div className={styles.heading}>
            <div><h2>{mode === 'simulated' ? '모의투자' : '실전투자'} 대시보드</h2><p>{user ? `@${user.username}` : ''}</p></div>
            <button className={styles.modeButton} onClick={() => navigate('/dashboard')}>홈으로</button>
          </div>
          <MarketTicker />
          {error && <p className={styles.error}>{error}</p>}

          {liveAccessPending ? (
            <section className={styles.dashboardSection}>
              <div className={styles.sectionHeading}><div><h3>실전투자 연결 상태 확인 중</h3></div></div>
            </section>
          ) : liveBlocked ? (
            <section className={styles.dashboardSection}>
              <div className={styles.sectionHeading}>
                <div>
                  <h3>Upbit API 연결이 필요합니다</h3>
                  <p>API Key를 등록한 후 실전투자 전략과 실제 계좌를 관리할 수 있습니다.</p>
                </div>
                <button className={styles.modeButton} onClick={() => navigate('/settings?highlight=api')}>API Key 등록하기</button>
              </div>
            </section>
          ) : (
            <>
              {mode === 'live' && (
                <section className={styles.dashboardSection}>
                  <div className={styles.sectionHeading}>
                    <div>
                      <h3>포트폴리오 배정</h3>
                      <p>지금 운용 중인 자산과, 전략마다 얼마씩 배정됐는지 한눈에 확인해요.</p>
                    </div>
                  </div>
                  <PortfolioPanel />
                </section>
              )}
              <section className={styles.dashboardSection}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h3>{mode === 'simulated' ? '모의계좌' : '실전계좌'}</h3>
                    <p>{mode === 'simulated' ? '가상의 자금으로 모의투자를 진행하며, 코인 시세는 Upbit를 기준으로 사용합니다.' : '실제 자금으로 자동매매를 진행하며, Upbit 실계좌 잔고를 그대로 보여드려요.'}</p>
                  </div>
                </div>
                {mode === 'simulated' && <PaperAccountPanel />}
                {mode === 'live' && <BalancePanel />}
              </section>

              <section className={styles.dashboardSection}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h3>전략 관리</h3>
                    <p>사용할 전략을 선택하고 투자 비율과 자동 청산 조건을 설정합니다.</p>
                  </div>
                </div>
                <StrategyPanel executionMode={mode} />
              </section>

              <section className={styles.dashboardSection}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h3>자동매매 기록</h3>
                    <p>전략이 감지한 신호와 사용자 계정에 반영된 실행 결과를 확인합니다.</p>
                  </div>
                </div>
                <ActivityPanel mode={mode} />
              </section>
            </>
          )}

        </section>

        <footer className={styles.footer}>
          <span>© 2026 SignalTrade. All rights reserved.</span>
        </footer>
      </main>
    </div>
  )
}
