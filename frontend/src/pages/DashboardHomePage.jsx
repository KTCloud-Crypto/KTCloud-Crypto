import MarketTicker from '../components/dashboard/MarketTicker'
import { serviceReadiness } from '../utils/serviceReadiness'
import { useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  CircleDollarSign,
  FlaskConical,
  ShieldAlert,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import { apiFetch, clearToken } from '../api/client'
import { usePolling } from '../hooks/usePolling'
import { formatNumber } from '../utils/format'
import styles from './DashboardHomePage.module.css'

const SUMMARY_REFRESH_INTERVAL_MS = 15_000

const EMPTY_SUMMARY = {
  strategies: [],
  positions: [],
}

function ModeCard({ mode, summary, loading, onEnter }) {
  const simulated = mode === 'simulated'
  const activeStrategies = summary.strategies.filter((item) => item.selected)
  const activeStrategyCount = summary.activeStrategyCount ?? activeStrategies.length
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
          </>
        )}
        <span><small>활성 전략</small><strong>{activeStrategyCount}개</strong></span>
        <span>
          <small>보유 포지션</small>
          <strong>{holdingCount}개{!simulated && ` · 코인 ${summary.coinCount ?? '-'}종`}</strong>
        </span>
      </div>

      <button onClick={onEnter}>
        {simulated ? '모의투자 관리' : '실전투자 관리'}
        <ArrowRight size={17} />
      </button>

      {!simulated && summary.mismatchCount > 0 && (
        <div className={styles.warning}>
          <AlertTriangle size={16} />
          <span>
            <strong>잔고 불일치 {summary.mismatchCount}건을 확인해 주세요.</strong>
            <small>텔레그램에서 <code>/sync</code> 메시지를 보내 잔고를 동기화하면 이 안내가 사라집니다.</small>
          </span>
        </div>
      )}
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

  const loadSummary = async () => {
    const meResult = await Promise.allSettled([apiFetch('/users/me')])
    if (meResult[0].status === 'rejected') {
      setLoadWarnings(['profile'])
      setLoading(false)
      return
    }

    const me = meResult[0].value
    const results = await Promise.allSettled([
      apiFetch('/paper-account'),
      apiFetch('/strategies?mode=simulated'),
      apiFetch('/strategies/positions?mode=simulated&all_markets=true'),
      apiFetch('/strategies/positions?mode=live&all_markets=true'),
      apiFetch('/strategies/allocation?mode=simulated'),
      apiFetch('/strategies/allocation?mode=live'),
    ])
    const liveResults = me.has_api_key
      ? await Promise.allSettled([
          apiFetch('/positions/balance'),
          apiFetch('/positions/reconciliation'),
          apiFetch('/positions/summary'),
        ])
      : []
    const value = (index, fallback) => results[index].status === 'fulfilled' ? results[index].value : fallback
    const liveValue = (index, fallback) => liveResults[index]?.status === 'fulfilled' ? liveResults[index].value : fallback
    const balances = liveValue(0, [])
    const krw = balances.find((item) => item.currency === 'KRW')
    setUser(me)
    setPaper({
      account: value(0, null),
      strategies: value(1, []),
      positions: value(2, []),
      activeStrategyCount: value(4, {}).active_count,
      totalAllocation: (value(4, {}).total_ratio ?? 0) * 100,
    })
    setLive({
      strategies: [],
      positions: value(3, []),
      krwBalance: krw?.balance,
      coinCount: me.has_api_key
        ? balances.filter((item) => item.currency !== 'KRW' && item.balance + item.locked > 0).length
        : null,
      mismatchCount: liveValue(1, []).filter((item) => item.status !== 'matched').length,
      account: liveValue(2, null),
      activeStrategyCount: value(5, {}).active_count,
      totalAllocation: (value(5, {}).total_ratio ?? 0) * 100,
      exchangeConnected: me.has_api_key && liveResults[0]?.status === 'fulfilled',
    })
    setLoadWarnings([...results, ...liveResults]
      .map((result, index) => ({ result, index }))
      .filter(({ result }) => result.status === 'rejected')
      .map(({ index }) => index))
    setLoading(false)
  }

  usePolling(loadSummary, SUMMARY_REFRESH_INTERVAL_MS)

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  const paperActiveCount = paper.activeStrategyCount ?? paper.strategies.filter((item) => item.selected).length
  const liveActiveCount = live.activeStrategyCount ?? live.strategies.filter((item) => item.selected).length

  return (
    <div className={styles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout} />
      <main className={styles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} user={user} mode="home" readiness={serviceReadiness(user)} />
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

          <MarketTicker />

          {loadWarnings.length > 0 && !loading && (
            <div className={styles.loadWarning}><AlertTriangle size={17} /> 일부 계좌 정보를 불러오지 못했습니다. 각 투자 화면에서 연결 상태를 확인해 주세요.</div>
          )}

          <section className={styles.modeGrid}>
            <ModeCard mode="simulated" summary={paper} loading={loading} onEnter={() => navigate('/dashboard/simulated')} />
            <ModeCard mode="live" summary={live} loading={loading} onEnter={() => navigate('/dashboard/live')} />
          </section>

          <section className={styles.guide}>
            <span><CircleDollarSign size={20} /></span>
            <div><strong>처음 이용하시나요?</strong><p>모의투자에서 전략과 투자 비율을 검증한 뒤 실전투자를 시작하는 것을 권장합니다.</p></div>
            <button onClick={() => navigate('/guide')}>이용 가이드 보기 <ArrowRight size={16} /></button>
          </section>
        </div>
      </main>
    </div>
  )
}
