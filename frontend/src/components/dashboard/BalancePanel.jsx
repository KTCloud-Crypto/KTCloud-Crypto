import { useEffect, useState } from 'react'
import {
  Banknote,
  CalendarCheck2,
  ChartNoAxesCombined,
  ChevronDown,
  ChevronUp,
  Clock3,
  Hourglass,
  PieChart,
  RefreshCw,
  TrendingUp,
  WalletCards,
} from 'lucide-react'
import { apiFetch } from '../../api/client'
import { coinIconForCurrency, coinIconForMarket } from '../../utils/coinIcons'
import styles from './Panel.module.css'

function formatQuantity(value) {
  if (value === 0) return '0'
  return value.toLocaleString(undefined, { maximumFractionDigits: 8 })
}

function formatMoney(value) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

function idempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

export default function BalancePanel({ onOverviewChange, refreshToken = 0, showHeader = true }) {
  const [balances, setBalances] = useState([])
  const [reconciliation, setReconciliation] = useState([])
  const [account, setAccount] = useState(null)
  const [strategies, setStrategies] = useState([])
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [deductionDrafts, setDeductionDrafts] = useState({})
  const [deductionNotice, setDeductionNotice] = useState('')
  const [showAllStrategies, setShowAllStrategies] = useState(false)

  const load = () => {
    setLoading(true)
    setError('')
    Promise.allSettled([
      apiFetch('/positions/dashboard'),
      apiFetch('/positions/summary'),
    ])
      .then(([dashboardResult, summaryResult]) => {
        if (dashboardResult.status === 'rejected') throw dashboardResult.reason
        const dashboard = dashboardResult.value
        const reconciliationItems = dashboard.reconciliation
        const portfolio = dashboard.portfolio
        setBalances(dashboard.balances)
        setReconciliation(reconciliationItems)
        setAccount(dashboard.account)
        setStrategies((portfolio.strategies || []).filter((strategy) => strategy.enabled))
        setSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null)
        onOverviewChange?.({
          accountEquity: dashboard.account.account_equity,
          availableKrw: dashboard.account.available_krw,
          strategyReservedKrw: dashboard.account.strategy_reserved_krw,
          activeStrategies: (portfolio.strategies || []).filter((strategy) => strategy.enabled).length,
          reconciliationIssues: reconciliationItems.filter((item) => item.status === 'shortfall').length,
          updatedAt: Date.now(),
        })
        setDeductionDrafts((current) => Object.fromEntries(reconciliationItems
          .filter((item) => item.status === 'shortfall')
          .map((item) => [
          item.currency,
          current[item.currency] || {
            strategyId: item.strategies.find((strategy) => strategy.volume > 0)?.subscription_id || '',
            volume: Math.abs(item.difference),
          },
        ])))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [onOverviewChange, refreshToken])

  const applyDeduction = async (item) => {
    const draft = deductionDrafts[item.currency] || {}
    if (!draft.strategyId || !(Number(draft.volume) > 0)) {
      setError('차감할 전략과 수량을 확인해 주세요.')
      return
    }
    if (!window.confirm(`${item.currency} ${draft.volume}개를 선택한 전략에서 차감하시겠습니까? 실제 Upbit 주문은 실행되지 않습니다.`)) return
    setLoading(true)
    setError('')
    setDeductionNotice('')
    try {
      await apiFetch('/positions/reconciliation/deduct', {
        method: 'POST',
        body: JSON.stringify({
          currency: item.currency,
          expected_difference: item.difference,
          deductions: [{
            subscription_id: Number(draft.strategyId),
            volume: Number(draft.volume),
          }],
          idempotency_key: idempotencyKey(),
        }),
      })
      setDeductionNotice(`${item.currency} 전략 포지션 차감을 반영했습니다.`)
      load()
    } catch (requestError) {
      setError(requestError.message)
      setLoading(false)
    }
  }

  const accountAssets = account?.assets || []
  const unallocatedAssets = accountAssets.filter((item) => item.unallocated_volume > 0)
  const shortfalls = reconciliation.filter((item) => item.status === 'shortfall')
  const assetByCurrency = new Map(accountAssets.map((item) => [item.currency, item]))
  const visibleStrategies = showAllStrategies ? strategies : strategies.slice(0, 2)

  return (
    <article className={styles.panel}>
      {showHeader && (
        <header>
          <div><h3>실전계좌</h3><p>Upbit가 반환한 실제 계좌 잔고와 자산 구성을 보여드립니다.</p></div>
          <button className={styles.iconButton} onClick={load} disabled={loading} aria-label="새로고침"><RefreshCw size={18} /></button>
        </header>
      )}

      <div className={styles.content}>
      <div className={styles.accountIntro}>
        <h3>실전계좌 요약</h3>
        <p>Upbit 실계좌 기준의 현금, 코인 보유량과 외부 자산을 확인합니다.</p>
      </div>
      {error && <div className={styles.empty}>{error}</div>}
      {deductionNotice && <div className={styles.adjustmentNotice}>{deductionNotice}</div>}

      {account && (
        <div className={styles.summaryCards}>
          <SummaryCard icon={WalletCards} tone="blue" label="계좌 총 평가자산" value={`${formatMoney(account.account_equity)}원`} description="원화와 전체 코인 평가액" />
          <SummaryCard icon={Banknote} tone="purple" label="주문 가능 KRW" value={`${formatMoney(account.available_krw)}원`} description="즉시 주문 가능한 원화 잔고" />
          <SummaryCard icon={CalendarCheck2} tone="green" label="신규 전략 예약 가능 KRW" value={`${formatMoney(account.strategy_available_krw)}원`} description="새 전략에 배정 가능한 금액" />
          <SummaryCard icon={Clock3} tone="orange" label="미체결 전략 예약 KRW" value={`${formatMoney(account.strategy_reserved_krw)}원`} description="아직 매수되지 않은 전략 예산" />
          <SummaryCard icon={ChartNoAxesCombined} tone="blue" label="전략 관리 포지션" value={`${formatMoney(account.managed_positions_value)}원`} description="전략이 보유 중인 코인 평가액" />
          <SummaryCard icon={PieChart} tone="purple" label="외부/미배정 자산" value={`${formatMoney(account.unallocated_value)}원`} description="자동매매에서 제외된 코인" />
          <SummaryCard icon={Hourglass} tone="sky" label="주문 중 KRW" value={`${formatMoney(account.locked_krw)}원`} description="미체결 주문에 묶인 원화" />
          <SummaryCard
            icon={TrendingUp}
            tone={summary?.realized_profit_loss >= 0 ? 'green' : 'red'}
            label="전략 실현손익"
            value={summary ? `${summary.realized_profit_loss >= 0 ? '+' : ''}${formatMoney(summary.realized_profit_loss)}원` : '-'}
            description="매도가 끝난 누적 손익"
            valueTone={summary?.realized_profit_loss >= 0 ? 'positive' : 'negative'}
          />
        </div>
      )}

      {!error && (
        <section className={styles.strategySnapshotSection}>
          <div className={styles.sectionTitle}>
            <div><h4>활성 전략 현황</h4><p>현재 자동매매가 실행 중인 전략의 예산과 포지션을 요약합니다.</p></div>
            <span className={styles.strategyCount}>{strategies.length}개 활성</span>
          </div>
          {visibleStrategies.length > 0 ? (
            <div className={styles.strategySnapshotGrid}>
              {visibleStrategies.map((strategy) => (
                <article className={styles.strategySnapshot} key={`${strategy.strategy_id}-${strategy.market}`}>
                  <div className={styles.strategySnapshotHeader}>
                    <div className={styles.strategySnapshotIdentity}>
                      <MarketIcon market={strategy.market} />
                      <div><strong>{strategy.strategy_name}</strong><small>{strategy.market}</small></div>
                    </div>
                    <span>활성</span>
                  </div>
                  <div className={styles.strategySnapshotBody}>
                    <span><small>설정 방식</small><strong>{strategy.allocation_mode === 'amount' ? '금액 지정' : `${(strategy.invest_ratio * 100).toFixed(1)}%`}</strong></span>
                    <span><small>주문 예산</small><strong>{formatMoney(strategy.allocation_amount)}원</strong></span>
                    <span><small>현재 포지션</small><strong>{formatMoney(strategy.current_position_value)}원</strong></span>
                  </div>
                </article>
              ))}
            </div>
          ) : !loading && <div className={styles.empty}>현재 활성화된 실전투자 전략이 없습니다.</div>}
          {strategies.length > 2 && (
            <button className={styles.strategyToggle} onClick={() => setShowAllStrategies((current) => !current)}>
              {showAllStrategies ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              {showAllStrategies ? '접기' : `전략 ${strategies.length - 2}개 더 보기`}
            </button>
          )}
        </section>
      )}

      {!error && (
        <section className={`${styles.accountSection} ${styles.accountPrimarySection}`}>
          <div className={styles.sectionTitle}>
            <div><h4>실제 보유 잔고</h4><p>Upbit 계좌가 현재 보유한 원화와 코인입니다.</p></div>
          </div>
          <div className={styles.scroll}>
            <table className={styles.assetTable}>
              <thead><tr><th>자산</th><th>주문 가능</th><th>총 보유</th><th>평균 매수가</th><th>현재가</th><th>평가액</th></tr></thead>
              <tbody>
                {balances.map((item) => {
                  const asset = assetByCurrency.get(item.currency)
                  const total = item.balance + item.locked
                  const evaluation = item.currency === 'KRW' ? total : asset?.evaluation_amount
                  return (
                    <tr key={item.currency}>
                      <td><AssetIdentity currency={item.currency} /></td>
                      <td>{formatQuantity(item.balance)}</td>
                      <td><strong>{formatQuantity(total)}</strong></td>
                      <td>{item.currency === 'KRW' ? '-' : `${formatMoney(item.avg_buy_price)}원`}</td>
                      <td>{asset?.current_price == null ? '-' : `${formatMoney(asset.current_price)}원`}</td>
                      <td>{evaluation == null ? '-' : `${formatMoney(evaluation)}원`}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {!loading && balances.length === 0 && <div className={styles.empty}>Upbit 계좌에 표시할 잔고가 없습니다.</div>}
        </section>
      )}

      {!error && (unallocatedAssets.length > 0 || shortfalls.length > 0) && (
        <div className={styles.accountConditionGrid}>
      {account && unallocatedAssets.length > 0 && (
        <section className={styles.accountSection}>
          <div className={styles.sectionTitle}>
            <div><h4>외부/미배정 자산</h4><p>실제 계좌에는 있지만 SignalTrade 전략이 관리하지 않는 읽기 전용 자산입니다.</p></div>
          </div>
          <div className={styles.scroll}>
            <table className={styles.assetTable}>
              <thead><tr><th>자산</th><th>미배정 수량</th><th>현재가</th><th>평가액</th><th>지원 상태</th></tr></thead>
              <tbody>{unallocatedAssets.map((item) => (
                <tr key={item.currency}>
                  <td><AssetIdentity currency={item.currency} /></td>
                  <td>{formatQuantity(item.unallocated_volume)}</td>
                  <td>{item.current_price == null ? '-' : `${formatMoney(item.current_price)}원`}</td>
                  <td>{item.unallocated_value == null ? '-' : `${formatMoney(item.unallocated_value)}원`}</td>
                  <td><span className={item.supported ? styles.neutral : styles.failed}>{item.supported ? '지원 종목' : '조회 전용'}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      {shortfalls.length > 0 && (
        <section className={styles.accountSection}>
          <div className={styles.sectionTitle}>
            <div><h4>잔고 정합성</h4><p>실제 잔고가 전략 기록보다 부족한 경우에만 조치가 필요합니다.</p></div>
            <span className={styles.failed}>확인 필요 {shortfalls.length}건</span>
          </div>
          <div className={styles.accountCardList}>
            {shortfalls.map((item) => (
              <div
                key={item.currency}
                className={`${styles.reconciliationCard} ${styles.reconciliationCardWarn}`}
              >
                <div className={styles.accountCardHeader}>
                  <AssetIdentity currency={item.currency} />
                  <span className={styles.failed}>실제 잔고 부족</span>
                </div>
                <div className={styles.accountCardMetrics}>
                  <span><small>Upbit 총보유량</small><strong>{formatQuantity(item.actual_total)}</strong></span>
                  <span><small>전략 기록 수량</small><strong>{formatQuantity(item.strategy_volume)}</strong></span>
                  <span><small>차이</small><strong>{item.difference > 0 ? '+' : ''}{formatQuantity(item.difference)}</strong></span>
                </div>
                <small className={styles.error}>{item.message}</small>
                {item.status === 'shortfall' && item.strategies.some((strategy) => strategy.volume > 0) && (
                  <div className={styles.deductionControls}>
                    <select
                      value={deductionDrafts[item.currency]?.strategyId || ''}
                      onChange={(event) => setDeductionDrafts((current) => ({
                        ...current,
                        [item.currency]: { ...current[item.currency], strategyId: event.target.value },
                      }))}
                    >
                      {item.strategies
                        .filter((strategy) => strategy.volume > 0)
                        .map((strategy) => <option key={strategy.subscription_id} value={strategy.subscription_id}>{strategy.market} · {strategy.strategy_name} ({formatQuantity(strategy.volume)})</option>)}
                    </select>
                    <input
                      type="number"
                      min="0.00000001"
                      step="0.00000001"
                      value={deductionDrafts[item.currency]?.volume ?? ''}
                      onChange={(event) => setDeductionDrafts((current) => ({
                        ...current,
                        [item.currency]: { ...current[item.currency], volume: event.target.value },
                      }))}
                    />
                    <button onClick={() => applyDeduction(item)} disabled={loading}>전략에서 차감</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
        </div>
      )}
      </div>
    </article>
  )
}

function SummaryCard({ icon: Icon, tone, label, value, description, valueTone = '' }) {
  return (
    <article className={styles.summaryCard}>
      <span className={`${styles.summaryIcon} ${styles[`summaryIcon${tone}`]}`}><Icon size={21} /></span>
      <div>
        <small>{label}</small>
        <strong className={valueTone ? styles[valueTone] : ''}>{value}</strong>
        <p>{description}</p>
      </div>
    </article>
  )
}

function AssetIdentity({ currency }) {
  const icon = coinIconForCurrency(currency)
  return (
    <span className={styles.assetIdentity}>
      <span className={styles.assetIdentityIcon}>
        <span>{currency.slice(0, 2)}</span>
        <img src={icon} alt="" onError={(event) => event.currentTarget.remove()} />
      </span>
      <strong>{currency}</strong>
    </span>
  )
}

function MarketIcon({ market }) {
  const currency = market?.split('-').at(-1) || ''
  const icon = coinIconForMarket(market)
  return (
    <span className={styles.strategyMarketIcon} aria-hidden="true">
      <span>{currency.slice(0, 2)}</span>
      <img src={icon} alt="" onError={(event) => event.currentTarget.remove()} />
    </span>
  )
}
