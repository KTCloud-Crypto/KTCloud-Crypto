import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, CircleDollarSign, RefreshCw, Target, TrendingUp } from 'lucide-react'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import { apiFetch, clearToken } from '../api/client'
import layoutStyles from './DashboardPage.module.css'
import styles from './AnalyticsPage.module.css'

const COLORS = ['#5574f7', '#20ad83', '#f3a23a', '#8a62e8', '#ed5b68', '#35a5dd', '#6f7d95', '#d06ba8', '#62b65d', '#b98a58']
const won = (value) => `${Math.round(value || 0).toLocaleString()}원`

export default function AnalyticsPage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [data, setData] = useState(null)
  const [period, setPeriod] = useState('month')
  const [investmentMode, setInvestmentMode] = useState('live')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [me, analytics] = await Promise.all([apiFetch('/users/me'), apiFetch(`/analytics?mode=${investmentMode}`)])
      setUser(me); setData(analytics)
    } catch (err) { setError(err.message) } finally { setLoading(false) }
  }, [investmentMode])
  useEffect(() => { load() }, [load])
  const logout = () => { clearToken(); navigate('/login', { replace: true }) }
  const metric = data?.[period] || data?.month

  const donut = useMemo(() => {
    if (!data?.tickers?.length) return '#e9edf5 0 100%'
    let start = 0
    return data.tickers.map((ticker, index) => {
      const end = start + ticker.weight
      const section = `${COLORS[index % COLORS.length]} ${start}% ${end}%`
      start = end
      return section
    }).join(', ')
  }, [data])

  return (
    <div className={layoutStyles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout} activePage="analytics" />
      <main className={layoutStyles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} user={user} mode={investmentMode} />
        <section className={`${layoutStyles.content} ${styles.content}`}>
          <header className={styles.pageHeader}>
            <div><h2>수익 분석</h2><p>수수료를 제외한 FIFO 기준 실현손익입니다.</p></div>
            <div className={styles.headerActions}>
              <div className={styles.modeSwitch} aria-label="투자 유형 선택">
                <button className={investmentMode === 'live' ? styles.selectedMode : ''} onClick={() => setInvestmentMode('live')}>실전투자</button>
                <button className={investmentMode === 'simulated' ? styles.selectedMode : ''} onClick={() => setInvestmentMode('simulated')}>모의투자</button>
              </div>
              <button className={styles.refreshButton} onClick={load} disabled={loading}><RefreshCw size={16} />{loading ? '분석 중' : '새로고침'}</button>
            </div>
          </header>
          {error && <p className={styles.error}>{error}</p>}
          {!error && <>
            <div className={styles.periods}>{[['today','오늘'],['week','이번 주'],['month','이번 달'],['all_time','전체']].map(([key,label]) => <button key={key} className={period === key ? styles.active : ''} onClick={() => setPeriod(key)}>{label}</button>)}</div>
            <section className={styles.metrics}>
              <Metric icon={CircleDollarSign} label="실현손익" value={won(metric?.realized_pnl)} tone={(metric?.realized_pnl || 0) >= 0 ? 'up' : 'down'} />
              <Metric icon={Target} label="매도 승률" value={`${metric?.win_rate || 0}%`} sub={`${metric?.win_count || 0}/${metric?.sell_count || 0}회`} />
              <Metric icon={Activity} label="체결 거래" value={`${metric?.trade_count || 0}건`} />
              <Metric icon={TrendingUp} label="평가 손익" value={won(metric?.unrealized_pnl || 0)} />
            </section>

            <section className={styles.chartGrid}>
              <article className={styles.card}><div className={styles.cardHead}><h3>종목별 거래 비중</h3><p>누적 체결금액 기준</p></div><div className={styles.donutArea}>
                <div className={styles.donut} style={{ background: `conic-gradient(${donut})` }}><div><strong>{data?.tickers?.length || 0}</strong><span>거래 종목</span></div></div>
                <div className={styles.legend}>{data?.tickers?.slice(0, 6).map((ticker, index) => <div key={ticker.ticker}><i style={{ background: COLORS[index] }} /><span>{ticker.ticker.replace('KRW-', '')}</span><strong>{ticker.weight}%</strong></div>)}</div>
              </div>{!data?.tickers?.length && <Empty />}</article>

              <article className={styles.card}><div className={styles.cardHead}><h3>30일 누적 실현손익</h3><p>일별 매도 체결 기준</p></div><PnlChart points={data?.daily_pnl || []} /></article>
            </section>

            <article className={styles.card}><div className={styles.cardHead}><h3>종목별 성과</h3><p>실현손익과 거래 규모 비교</p></div>
              <div className={styles.performance}>{data?.tickers?.map((ticker, index) => {
                const max = Math.max(...data.tickers.map((item) => Math.abs(item.realized_pnl)), 1)
                return <div className={styles.performanceRow} key={ticker.ticker}><div><i style={{ background: COLORS[index] }} /><strong>{ticker.ticker}</strong><span>{ticker.trade_count}건</span></div><div className={styles.barTrack}><span className={ticker.realized_pnl >= 0 ? styles.positiveBar : styles.negativeBar} style={{ width: `${Math.max(Math.abs(ticker.realized_pnl) / max * 100, 2)}%` }} /></div><b className={ticker.realized_pnl >= 0 ? styles.up : styles.down}>{won(ticker.realized_pnl)}</b></div>
              })}</div>{!data?.tickers?.length && <Empty />}
            </article>
            <p className={styles.disclaimer}>가격 또는 체결수량이 없는 미완료·실패 거래 {data?.excluded_trade_count || 0}건은 분석에서 제외했습니다. {investmentMode === 'live' ? 'Upbit 수수료 데이터는 현재 저장되지 않아 손익에 포함하지 않았습니다.' : '모의투자 체결 기록을 기준으로 계산했습니다.'}</p>
          </>}
        </section>
      </main>
    </div>
  )
}

function Metric({ icon: Icon, label, value, sub, tone }) { return <article className={styles.metric}><span><Icon size={18} /></span><div><p>{label}</p><strong className={tone ? styles[tone] : ''}>{value}</strong>{sub && <small>{sub}</small>}</div></article> }
function Empty() { return <p className={styles.empty}>분석할 체결 거래가 없습니다.</p> }

function PnlChart({ points }) {
  const [hoveredIndex, setHoveredIndex] = useState(null)
  const values = points.map((point) => point.cumulative_pnl)
  const min = Math.min(...values, 0), max = Math.max(...values, 0), range = max - min || 1
  const coords = points.map((point, index) => `${(index / Math.max(points.length - 1, 1)) * 100},${92 - ((point.cumulative_pnl - min) / range) * 78}`).join(' ')
  const zeroY = 92 - ((0 - min) / range) * 78
  const positive = (values.at(-1) || 0) >= 0
  const zeroPercent = Math.max(0, Math.min(100, zeroY))

  // Y축 눈금 계산 (5개)
  const ticks = Array.from({ length: 5 }, (_, i) => {
    const value = max - (i * (max - min) / 4)
    const y = 92 - ((value - min) / range) * 78
    return { value, y }
  })

  const handleMouseMove = (event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width
    const index = Math.round(x * (points.length - 1))
    setHoveredIndex(Math.max(0, Math.min(index, points.length - 1)))
  }

  const hoveredPoint = hoveredIndex !== null ? points[hoveredIndex] : null
  const hoveredX = hoveredIndex !== null ? (hoveredIndex / Math.max(points.length - 1, 1)) * 100 : null
  const hoveredY = hoveredPoint ? 92 - ((hoveredPoint.cumulative_pnl - min) / range) * 78 : null

  return (
    <div className={styles.lineChart}>
      <div className={styles.chartValue}>
        <strong className={positive ? styles.up : styles.down}>{won(values.at(-1))}</strong>
        <span>최근 30일 누적</span>
      </div>
      <div className={styles.yAxis}>
        {ticks.map((tick, i) => (
          <span key={i} style={{ top: `${tick.y}%` }}>{won(tick.value)}</span>
        ))}
      </div>
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        role="img"
        aria-label="30일 누적 실현손익 그래프"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredIndex(null)}
        style={{ cursor: 'crosshair' }}
      >
        <defs>
          <linearGradient id="pnlLineGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset={`${zeroPercent}%`} stopColor="#20ad83" />
            <stop offset={`${zeroPercent}%`} stopColor="#ed5b68" />
          </linearGradient>
        </defs>
        <line x1="0" y1={zeroY} x2="100" y2={zeroY} className={styles.zeroLine} />
        <polyline points={coords} className={styles.pnlLine} />
        {hoveredX !== null && (
          <>
            <line x1={hoveredX} y1="0" x2={hoveredX} y2="100" className={styles.hoverLine} />
            <circle cx={hoveredX} cy={hoveredY} r="0.8" className={styles.hoverDot} />
          </>
        )}
      </svg>
      {hoveredPoint && (
        <div
          className={styles.tooltip}
          style={{
            left: `${hoveredX}%`,
            transform: hoveredX > 50 ? 'translateX(-100%)' : 'translateX(0)'
          }}
        >
          <div className={styles.tooltipDate}>{hoveredPoint.date}</div>
          <div className={styles.tooltipValue}>
            <span>누적 손익</span>
            <strong className={hoveredPoint.cumulative_pnl >= 0 ? styles.up : styles.down}>
              {won(hoveredPoint.cumulative_pnl)}
            </strong>
          </div>
          <div className={styles.tooltipValue}>
            <span>당일 손익</span>
            <strong className={hoveredPoint.daily_pnl >= 0 ? styles.up : styles.down}>
              {won(hoveredPoint.daily_pnl)}
            </strong>
          </div>
        </div>
      )}
      <div className={styles.axis}>
        <span>{points[0]?.date?.slice(5)}</span>
        <span>{points.at(-1)?.date?.slice(5)}</span>
      </div>
    </div>
  )
}
