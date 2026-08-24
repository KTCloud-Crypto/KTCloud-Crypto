import MarketTicker from '../components/dashboard/MarketTicker'
import { serviceReadiness } from '../utils/serviceReadiness'
import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import SiteHeader from '../components/layout/SiteHeader'
import BalancePanel from '../components/dashboard/BalancePanel'
import StrategyPanel from '../components/dashboard/StrategyPanel'
import ActivityPanel from '../components/dashboard/ActivityPanel'
import PaperAccountPanel from '../components/dashboard/PaperAccountPanel'
import { apiFetch, clearToken } from '../api/client'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { mode } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')
  const [accountOverview, setAccountOverview] = useState(null)
  const [accountRefreshToken, setAccountRefreshToken] = useState(0)

  const requestedTab = searchParams.get('tab')
  const dashboardTab = ['account', 'strategies', 'activity'].includes(requestedTab) ? requestedTab : 'account'

  useEffect(() => {
    setAccountOverview(null)
  }, [mode])

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
  const formatWon = (value) => value == null ? '-' : `${Math.round(value).toLocaleString()}원`
  const lastUpdated = accountOverview?.updatedAt
    ? new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit' }).format(accountOverview.updatedAt)
    : '불러오는 중'

  const selectDashboardTab = (tab) => {
    setSearchParams({ tab })
  }

  return (
    <div className={styles.app}>
      <SiteHeader user={user} readiness={serviceReadiness(user)} onLogout={handleLogout} />

      <main className={styles.main}>
        <section className={styles.content}>
          <div className={styles.livePageHeader}>
            <div>
              <h1>{mode === 'live' ? '실전투자 대시보드' : '모의투자 대시보드'}</h1>
              <p>
                {mode === 'live'
                  ? '실제 자금으로 자동매매가 실행되는 계좌의 핵심 현황을 확인하세요.'
                  : '가상 자금으로 실전과 같은 자동매매 흐름을 연습하고 관리하세요.'}
              </p>
            </div>
            {!liveBlocked && !liveAccessPending && (
              <div className={styles.refreshStatus}>
                <button onClick={() => setAccountRefreshToken((current) => current + 1)}>
                  <RefreshCw size={17} /> 새로고침
                </button>
                <span>마지막 업데이트 {lastUpdated}</span>
              </div>
            )}
          </div>
          <MarketTicker />
          {error && <p className={styles.error}>{error}</p>}

          {!liveBlocked && !liveAccessPending && (
            <>
              <section className={styles.liveOverview} aria-label={`${mode === 'live' ? '실전' : '모의'}투자 핵심 현황`}>
                <span>
                  <small>{mode === 'live' ? '계좌 총 평가자산' : '모의 총 평가자산'}</small>
                  <strong>{formatWon(accountOverview?.accountEquity)}</strong>
                  <em>{mode === 'live' ? '원화와 전체 코인 평가액' : '가상 현금과 보유 포지션 평가액'}</em>
                </span>
                <span>
                  <small>미체결 전략 예약 KRW</small>
                  <strong>{formatWon(accountOverview?.strategyReservedKrw)}</strong>
                  <em>아직 매수되지 않은 전략 예산</em>
                </span>
                <span>
                  <small>활성 전략</small>
                  <strong>{accountOverview ? `${accountOverview.activeStrategies}개` : '-'}</strong>
                  <em>자동매매 전략 실행 중</em>
                </span>
                {mode === 'live' ? (
                  <span>
                    <small>잔고 정합성</small>
                    <strong className={accountOverview?.reconciliationIssues > 0 ? styles.overviewWarning : styles.overviewReady}>
                      {accountOverview ? (accountOverview.reconciliationIssues > 0 ? `확인 필요 ${accountOverview.reconciliationIssues}건` : '정상') : '-'}
                    </strong>
                    <em>실제 잔고 부족 여부</em>
                  </span>
                ) : (
                  <span>
                    <small>모의 누적 손익</small>
                    <strong className={(accountOverview?.profitLoss ?? 0) >= 0 ? styles.overviewReady : styles.overviewWarning}>
                      {accountOverview ? `${accountOverview.profitLoss >= 0 ? '+' : ''}${formatWon(accountOverview.profitLoss)}` : '-'}
                    </strong>
                    <em>보유 포지션의 현재 평가액을 포함한 성과</em>
                  </span>
                )}
              </section>

              <nav className={styles.liveTabs} aria-label={`${mode === 'live' ? '실전' : '모의'}투자 화면 선택`}>
                <button className={dashboardTab === 'account' ? styles.activeTab : ''} onClick={() => selectDashboardTab('account')}>계좌 현황</button>
                <button className={dashboardTab === 'strategies' ? styles.activeTab : ''} onClick={() => selectDashboardTab('strategies')}>전략 관리</button>
                <button className={dashboardTab === 'activity' ? styles.activeTab : ''} onClick={() => selectDashboardTab('activity')}>자동매매 활동</button>
              </nav>
            </>
          )}

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
            <div className={styles.liveWorkspace}>
              <section className={styles.liveTabPanel} hidden={dashboardTab !== 'account'}>
                {mode === 'live' ? (
                  <BalancePanel
                    onOverviewChange={setAccountOverview}
                    refreshToken={accountRefreshToken}
                    showHeader={false}
                  />
                ) : (
                  <PaperAccountPanel
                    onOverviewChange={setAccountOverview}
                    refreshToken={accountRefreshToken}
                    showHeader={false}
                  />
                )}
              </section>

              <section className={styles.liveTabPanel} hidden={dashboardTab !== 'strategies'}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h3>전략 관리</h3>
                    <p>사용할 전략을 선택하고 투자 비율과 자동 청산 조건을 설정합니다.</p>
                  </div>
                </div>
                <StrategyPanel executionMode={mode} />
              </section>

              <section className={styles.liveTabPanel} hidden={dashboardTab !== 'activity'}>
                <div className={styles.sectionHeading}>
                  <div>
                    <h3>자동매매 활동</h3>
                    <p>전략이 감지한 신호와 {mode === 'live' ? '실제 계좌' : '모의 계좌'}에 반영된 실행 결과를 확인합니다.</p>
                  </div>
                </div>
                <ActivityPanel mode={mode} />
              </section>
            </div>
          )}

        </section>

        <footer className={styles.footer}>
          <span>© 2026 SignalTrade. All rights reserved.</span>
        </footer>
      </main>
    </div>
  )
}
