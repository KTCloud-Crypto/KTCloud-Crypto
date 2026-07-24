import { useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BellRing,
  CheckCircle2,
  CircleDollarSign,
  FlaskConical,
  ShieldAlert,
  WalletCards,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import { apiFetch, clearToken } from '../api/client'
import { formatNumber } from '../utils/format'
import styles from './DashboardHomePage.module.css'

const EMPTY_SUMMARY = {
  strategies: [],
  positions: [],
}

function ModeCard({ mode, summary, loading, onEnter }) {
  const simulated = mode === 'simulated'
  const activeStrategies = summary.strategies.filter((item) => item.selected)
  const activeStrategyCount = summary.activeStrategyCount ?? activeStrategies.length
  const allocation = summary.totalAllocation ?? activeStrategies.reduce((total, item) => total + item.invest_ratio * 100, 0)
  const holdingCount = summary.positions.filter((item) => (
    simulated ? item.paper_status === 'holding' : item.status === 'holding'
  )).length

  return (
    <article className={`${styles.modeCard} ${simulated ? styles.paperCard : styles.liveCard}`}>
      <header>
        <span className={styles.modeIcon}>{simulated ? <FlaskConical size={24} /> : <ShieldAlert size={24} />}</span>
        <div>
          <small>{simulated ? 'PAPER TRADING' : 'LIVE TRADING'}</small>
          <h2>{simulated ? '모의투자' : '실전투자'}</h2>
        </div>
        <span className={styles.modeState}>{loading ? '불러오는 중' : '운영 현황'}</span>
      </header>

      <div className={styles.modeMetrics}>
        {simulated ? (
          <>
            <span><small>총 평가금액</small><strong>{formatNumber(summary.account?.total_equity)}원</strong></span>
            <span className={(summary.account?.profit_loss ?? 0) >= 0 ? styles.positive : styles.negative}>
              <small>총 손익</small>
              <strong>{(summary.account?.profit_loss ?? 0) >= 0 ? '+' : ''}{formatNumber(summary.account?.profit_loss)}원</strong>
            </span>
          </>
        ) : (
          <>
            <span><small>KRW 가용 잔고</small><strong>{formatNumber(summary.krwBalance)}원</strong></span>
            <span className={(summary.account?.profit_loss ?? 0) >= 0 ? styles.positive : styles.negative}>
              <small>총 손익</small>
              <strong>
                {(summary.account?.profit_loss ?? 0) >= 0 ? '+' : ''}
                {formatNumber(summary.account?.profit_loss)}원
                {' '}
                ({summary.account?.return_rate == null ? '-' : `${summary.account.return_rate.toFixed(2)}%`})
              </strong>
            </span>
            <span><small>보유 코인</small><strong>{summary.coinCount ?? '-'}종</strong></span>
          </>
        )}
        <span><small>활성 전략</small><strong>{activeStrategyCount}개</strong></span>
        <span><small>투자 비율 합계</small><strong>{Math.round(allocation)}%</strong></span>
        <span><small>보유 포지션</small><strong>{holdingCount}개</strong></span>
      </div>

      {!simulated && summary.mismatchCount > 0 && (
        <div className={styles.warning}><AlertTriangle size={16} /> 잔고 불일치 {summary.mismatchCount}건을 확인해 주세요.</div>
      )}

      <button onClick={onEnter}>
        {simulated ? '모의투자 관리' : '실전투자 관리'}
        <ArrowRight size={17} />
      </button>
    </article>
  )
}

export default function DashboardHomePage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [paper, setPaper] = useState(EMPTY_SUMMARY)
  const [live, setLive] = useState(EMPTY_SUMMARY)
  const [loading, setLoading] = useState(true)
  const [loadWarnings, setLoadWarnings] = useState([])

  useEffect(() => {
    let active = true
    const loadSummary = async () => {
      const results = await Promise.allSettled([
        apiFetch('/users/me'),
        apiFetch('/paper-account'),
        apiFetch('/strategies?mode=simulated'),
        apiFetch('/strategies/positions?mode=simulated&all_markets=true'),
        apiFetch('/strategies?mode=live'),
        apiFetch('/strategies/positions?mode=live&all_markets=true'),
        apiFetch('/positions/balance'),
        apiFetch('/positions/reconciliation'),
        apiFetch('/positions/summary'),
        apiFetch('/strategies/allocation?mode=simulated'),
        apiFetch('/strategies/allocation?mode=live'),
      ])
      if (!active) return
      const value = (index, fallback) => results[index].status === 'fulfilled' ? results[index].value : fallback
      const balances = value(6, [])
      const krw = balances.find((item) => item.currency === 'KRW')
      setUser(value(0, null))
      setPaper({
        account: value(1, null),
        strategies: value(2, []),
        positions: value(3, []),
        activeStrategyCount: value(9, {}).active_count,
        totalAllocation: (value(9, {}).total_ratio ?? 0) * 100,
      })
      setLive({
        strategies: value(4, []),
        positions: value(5, []),
        krwBalance: krw?.balance,
        coinCount: balances.filter((item) => item.currency !== 'KRW' && item.balance + item.locked > 0).length,
        mismatchCount: value(7, []).filter((item) => item.status !== 'matched').length,
        account: value(8, null),
        activeStrategyCount: value(10, {}).active_count,
        totalAllocation: (value(10, {}).total_ratio ?? 0) * 100,
        exchangeConnected: results[6].status === 'fulfilled',
      })
      setLoadWarnings(results
        .map((result, index) => ({ result, index }))
        .filter(({ result }) => result.status === 'rejected')
        .map(({ index }) => index))
      setLoading(false)
    }

    loadSummary()
    const interval = window.setInterval(loadSummary, 5000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }
  const readiness = [
    {
      label: 'Upbit API',
      ready: live.exchangeConnected,
      detail: live.exchangeConnected ? '실계좌 조회 가능' : '연결 상태 확인 필요',
      icon: WalletCards,
    },
    {
      label: 'Telegram',
      ready: Boolean(user?.telegram_chat_id),
      detail: user?.telegram_chat_id ? '체결 알림 연결됨' : '알림 연결 필요',
      icon: BellRing,
    },
    {
      label: '자동매매',
      ready: Boolean(user?.bot_enabled),
      detail: user?.bot_enabled ? '신호 수신 활성화' : '현재 중지 상태',
      icon: Activity,
    },
  ]
  const paperActiveCount = paper.activeStrategyCount ?? paper.strategies.filter((item) => item.selected).length
  const liveActiveCount = live.activeStrategyCount ?? live.strategies.filter((item) => item.selected).length

  return (
    <div className={styles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout} />
      <main className={styles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} user={user} mode="home" />
        <div className={styles.content}>
          <section className={styles.hero}>
            <div>
              <span>SIGNALTRADE OVERVIEW</span>
              <h1>오늘의 투자 현황</h1>
              <p>상세 설정에 들어가기 전에 모의계좌와 실계좌의 핵심 상태를 확인합니다.</p>
            </div>
            <div className={styles.heroStrategies}>
              <div className={styles.heroStrategyMetric}>
                <FlaskConical size={20} />
                <span><small>모의 활성 전략</small><strong>{loading ? '-' : paperActiveCount}개</strong></span>
              </div>
              <div className={styles.heroStrategyMetric}>
                <ShieldAlert size={20} />
                <span><small>실전 활성 전략</small><strong>{loading ? '-' : liveActiveCount}개</strong></span>
              </div>
            </div>
          </section>

          {loadWarnings.length > 0 && !loading && (
            <div className={styles.loadWarning}><AlertTriangle size={17} /> 일부 계좌 정보를 불러오지 못했습니다. 각 투자 화면에서 연결 상태를 확인해 주세요.</div>
          )}

          <section className={styles.modeGrid}>
            <ModeCard mode="simulated" summary={paper} loading={loading} onEnter={() => navigate('/dashboard/simulated')} />
            <ModeCard mode="live" summary={live} loading={loading} onEnter={() => navigate('/dashboard/live')} />
          </section>

          <section className={styles.statusSection}>
            <div className={styles.sectionTitle}>
              <div><h2>서비스 준비 상태</h2><p>자동매매를 사용하기 위한 핵심 연결 상태입니다.</p></div>
            </div>
            <div className={styles.statusGrid}>
              {readiness.map((item) => {
                const Icon = item.icon
                return (
                  <article key={item.label}>
                    <span className={item.ready ? styles.readyIcon : styles.notReadyIcon}><Icon size={20} /></span>
                    <div><strong>{item.label}</strong><small>{item.detail}</small></div>
                    {item.ready ? <CheckCircle2 className={styles.check} size={19} /> : <AlertTriangle className={styles.alert} size={19} />}
                  </article>
                )
              })}
            </div>
          </section>

          <section className={styles.guide}>
            <span><CircleDollarSign size={20} /></span>
            <div><strong>처음 이용하시나요?</strong><p>모의투자에서 전략과 투자 비율을 검증한 뒤 실전투자를 시작하는 것을 권장합니다.</p></div>
            <button onClick={() => navigate('/dashboard/simulated')}>모의투자 시작 <ArrowRight size={16} /></button>
          </section>
        </div>
      </main>
    </div>
  )
}
