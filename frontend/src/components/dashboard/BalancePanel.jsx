import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { apiFetch } from '../../api/client'
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

export default function BalancePanel() {
  const [balances, setBalances] = useState([])
  const [reconciliation, setReconciliation] = useState([])
  const [strategies, setStrategies] = useState([])
  const [summary, setSummary] = useState(null)
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncDrafts, setSyncDrafts] = useState({})
  const [syncNotice, setSyncNotice] = useState('')

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
        setStrategies(portfolio.strategies || [])
        setAccount(dashboard.account)
        setSummary({
          realized_profit_loss: summaryResult.status === 'fulfilled'
            ? summaryResult.value.realized_profit_loss
            : null,
        })
        setSyncDrafts((current) => Object.fromEntries(reconciliationItems
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

  useEffect(load, [])

  const applySync = async (item) => {
    const draft = syncDrafts[item.currency] || {}
    if (!draft.strategyId || !(Number(draft.volume) > 0)) {
      setError('동기화할 전략과 수량을 확인해 주세요.')
      return
    }
    if (!window.confirm(`${item.currency} ${draft.volume}개를 선택한 전략에서 차감하시겠습니까? 실제 Upbit 주문은 실행되지 않습니다.`)) return
    setLoading(true)
    setError('')
    setSyncNotice('')
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
      setSyncNotice(`${item.currency} 전략 포지션 동기화를 반영했습니다.`)
      load()
    } catch (requestError) {
      setError(requestError.message)
      setLoading(false)
    }
  }

  const visibleStrategies = strategies.filter((strategy) => (
    strategy.enabled || strategy.current_position_value > 0
  ))

  return (
    <article className={styles.panel}>
      <header>
        <div><h3>실전계좌</h3><p>실제 자금으로 자동매매를 진행하며, Upbit 실계좌 잔고를 그대로 보여드려요.</p></div>
        <button className={styles.iconButton} onClick={load} disabled={loading} aria-label="새로고침"><RefreshCw size={18} /></button>
      </header>

      <div className={styles.content}>
      {error && <div className={styles.empty}>{error}</div>}
      {syncNotice && <div className={styles.syncNotice}>{syncNotice}</div>}

      {account && (
        <div className={styles.summaryCards}>
          <span>
            <small>계좌 총 평가자산</small>
            <strong className={styles.totalEquity}>{formatMoney(account.account_equity)}원</strong>
          </span>
          <span>
            <small>Upbit 주문 가능 KRW</small>
            <strong>{formatMoney(account.available_krw)}원</strong>
          </span>
          <span>
            <small>신규 전략 예약 가능 KRW</small>
            <strong>{formatMoney(account.strategy_available_krw)}원</strong>
          </span>
          <span>
            <small>미체결 전략 예약 KRW</small>
            <strong>{formatMoney(account.strategy_reserved_krw)}원</strong>
          </span>
          <span>
            <small>전략 관리 포지션</small>
            <strong>{formatMoney(account.managed_positions_value)}원</strong>
          </span>
          <span>
            <small>외부/미배정 자산</small>
            <strong>{formatMoney(account.unallocated_value)}원</strong>
          </span>
          <span><small>주문 중 KRW</small><strong>{formatMoney(account.locked_krw)}원</strong></span>
          {summary?.realized_profit_loss != null && (
            <span>
              <small>전략 실현손익</small>
              <strong className={summary.realized_profit_loss >= 0 ? styles.success : styles.failed}>
                {summary.realized_profit_loss >= 0 ? '+' : ''}{formatMoney(summary.realized_profit_loss)}원
              </strong>
            </span>
          )}
        </div>
      )}

      {!error && (
        <section className={styles.accountSection}>
          <h4 className={styles.subheading}>전략별 운용 현황</h4>
          <div className={styles.accountCardList}>
            {visibleStrategies.map((strategy) => (
              <div key={strategy.strategy_id + strategy.market} className={styles.allocationCard}>
                <div className={styles.accountCardHeader}>
                  <span className={styles.accountCardName}>
                    <strong>{strategy.strategy_name}</strong>
                    <small>{strategy.market}</small>
                  </span>
                  <span className={strategy.enabled ? styles.success : styles.neutral}>
                    {strategy.enabled ? '활성' : '비활성'}
                  </span>
                </div>
                <div className={styles.accountCardMetrics}>
                  <span>
                    <small>{strategy.allocation_mode === 'amount' ? '설정 방식' : '투자비율'}</small>
                    <strong>{strategy.allocation_mode === 'amount' ? '금액 지정' : `${(strategy.invest_ratio * 100).toFixed(1)}%`}</strong>
                  </span>
                  <span><small>주문 예산</small><strong>{formatMoney(strategy.allocation_amount)}원</strong></span>
                  <span><small>현재 포지션</small><strong>{formatMoney(strategy.current_position_value)}원</strong></span>
                </div>
              </div>
            ))}
          </div>
          {!loading && visibleStrategies.length === 0 && <div className={styles.empty}>활성화된 실전투자 전략이 없습니다.</div>}
        </section>
      )}

      {!error && (
        <section className={styles.accountSection}>
          <h4 className={styles.subheading}>보유 잔고</h4>
          <div className={styles.accountCardList}>
            {balances.map((item) => (
              <div key={item.currency} className={styles.balanceCard}>
                <div className={styles.accountCardHeader}>
                  <strong className={styles.balanceCurrency}>{item.currency}</strong>
                </div>
                <div className={styles.accountCardMetrics}>
                  <span><small>보유수량</small><strong>{formatQuantity(item.balance)}</strong></span>
                  <span><small>주문중수량</small><strong>{formatQuantity(item.locked)}</strong></span>
                  <span><small>평균매수가</small><strong>{formatQuantity(item.avg_buy_price)}원</strong></span>
                </div>
              </div>
            ))}
          </div>
          {!loading && balances.length === 0 && <div className={styles.empty}>보유 잔고가 없습니다.</div>}
        </section>
      )}

      {!error && account && (
        <section className={styles.accountSection}>
          <h4 className={styles.subheading}>외부/미배정 자산</h4>
          <div className={styles.accountCardList}>
            {account.assets.filter((item) => item.unallocated_volume > 0).map((item) => (
              <div key={item.currency} className={styles.balanceCard}>
                <div className={styles.accountCardHeader}>
                  <strong className={styles.balanceCurrency}>{item.currency}</strong>
                  <span className={item.supported ? styles.neutral : styles.failed}>
                    {item.supported ? '외부 보유' : '미지원 종목'}
                  </span>
                </div>
                <div className={styles.accountCardMetrics}>
                  <span><small>미배정 수량</small><strong>{formatQuantity(item.unallocated_volume)}</strong></span>
                  <span><small>평가액</small><strong>{item.unallocated_value == null ? '-' : `${formatMoney(item.unallocated_value)}원`}</strong></span>
                  <span><small>현재가</small><strong>{item.current_price == null ? '-' : `${formatMoney(item.current_price)}원`}</strong></span>
                </div>
              </div>
            ))}
          </div>
          {account.assets.every((item) => item.unallocated_volume <= 0) && (
            <div className={styles.empty}>외부/미배정 코인 자산이 없습니다.</div>
          )}
        </section>
      )}

      {!error && (
        <section className={styles.accountSection}>
          <h4 className={styles.subheading}>잔고 동기화 상태</h4>
          <div className={styles.accountCardList}>
            {reconciliation.map((item) => (
              <div
                key={item.currency}
                className={`${styles.syncCard} ${
                  item.status === 'matched' ? styles.syncCardOk
                    : item.status === 'external_balance' ? styles.syncCardNeutral
                      : styles.syncCardWarn
                }`}
              >
                <div className={styles.accountCardHeader}>
                  <strong className={styles.balanceCurrency}>{item.currency}</strong>
                  <span className={item.status === 'matched' ? styles.success : item.status === 'external_balance' ? styles.neutral : styles.failed}>
                    {item.status === 'matched' ? '일치' : item.status === 'external_balance' ? '외부 보유 수량 있음' : '실제 잔고 부족'}
                  </span>
                </div>
                <div className={styles.accountCardMetrics}>
                  <span><small>Upbit 총보유량</small><strong>{formatQuantity(item.actual_total)}</strong></span>
                  <span><small>전략 기록 수량</small><strong>{formatQuantity(item.strategy_volume)}</strong></span>
                  <span><small>차이</small><strong>{item.difference > 0 ? '+' : ''}{formatQuantity(item.difference)}</strong></span>
                </div>
                <small className={item.status !== 'matched' ? styles.error : styles.syncMessage}>{item.message}</small>
                {item.status === 'shortfall' && item.strategies.some((strategy) => strategy.volume > 0) && (
                  <div className={styles.syncControls}>
                    <select
                      value={syncDrafts[item.currency]?.strategyId || ''}
                      onChange={(event) => setSyncDrafts((current) => ({
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
                      value={syncDrafts[item.currency]?.volume ?? ''}
                      onChange={(event) => setSyncDrafts((current) => ({
                        ...current,
                        [item.currency]: { ...current[item.currency], volume: event.target.value },
                      }))}
                    />
                    <button onClick={() => applySync(item)} disabled={loading}>전략에서 차감</button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {!loading && reconciliation.length === 0 && <div className={styles.empty}>비교할 코인 잔고 또는 실전 전략 포지션이 없습니다.</div>}
        </section>
      )}
      </div>
    </article>
  )
}
