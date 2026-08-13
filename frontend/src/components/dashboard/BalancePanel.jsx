import { useEffect, useState } from 'react'
import { Info, RefreshCw } from 'lucide-react'
import { apiFetch } from '../../api/client'
import styles from './Panel.module.css'

function formatQuantity(value) {
  if (value === 0) return '0'
  return value.toLocaleString(undefined, { maximumFractionDigits: 8 })
}

function formatMoney(value) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function BalancePanel() {
  const [balances, setBalances] = useState([])
  const [reconciliation, setReconciliation] = useState([])
  const [strategies, setStrategies] = useState([])
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncDrafts, setSyncDrafts] = useState({})
  const [syncNotice, setSyncNotice] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    Promise.all([
      apiFetch('/positions/balance'),
      apiFetch('/positions/reconciliation'),
      apiFetch('/positions/portfolio'),
      apiFetch('/positions/summary'),
    ])
      .then(([balanceItems, reconciliationItems, portfolio, accountSummary]) => {
        setBalances(balanceItems)
        setReconciliation(reconciliationItems)
        setStrategies(portfolio.strategies || [])
        setSummary({
          available_krw: portfolio.available_krw,
          managed_positions_value: portfolio.managed_positions_value,
          total_equity: portfolio.total_equity,
          realized_profit_loss: accountSummary.realized_profit_loss,
        })
        setSyncDrafts((current) => Object.fromEntries(reconciliationItems.map((item) => [
          item.currency,
          current[item.currency] || {
            strategyId: (item.status === 'shortfall'
              ? item.strategies.find((strategy) => strategy.volume > 0)
              : item.strategies[0])?.subscription_id || '',
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
    const action = item.status === 'external_balance' ? 'buy' : 'sell'
    const verb = action === 'buy' ? '배정' : '차감'
    if (!window.confirm(`${item.currency} ${draft.volume}개를 선택한 전략에 ${verb}하시겠습니까? 실제 Upbit 주문은 실행되지 않습니다.`)) return
    setLoading(true)
    setError('')
    setSyncNotice('')
    try {
      await apiFetch('/positions/reconciliation/apply', {
        method: 'POST',
        body: JSON.stringify({
          subscription_id: Number(draft.strategyId),
          action,
          volume: Number(draft.volume),
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
    (strategy.strategy_code !== 'manual_hold_v1' || strategy.current_position_value > 0)
    && (strategy.enabled || strategy.current_position_value > 0)
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

      {summary && (
        <div className={styles.summaryCards}>
          <span>
            <small>주문 가능 현금</small>
            <strong>{formatMoney(summary.available_krw)}원</strong>
          </span>
          <span>
            <small>보유 평가액</small>
            <strong>{formatMoney(summary.managed_positions_value)}원</strong>
          </span>
          <span>
            <small>
              총 평가금액
              <span className={styles.tooltip}>
                <Info size={13} />
                <span className={styles.tooltipText}>
                  현금 + 보유 코인의 현재 평가액. 매수 신호 발생 시 이 금액을 기준으로 투자 비율이 계산됩니다.
                </span>
              </span>
            </small>
            <strong className={styles.totalEquity}>{formatMoney(summary.total_equity)}원</strong>
          </span>
          <span>
            <small>실현손익</small>
            <strong className={summary.realized_profit_loss >= 0 ? styles.success : styles.failed}>
              {summary.realized_profit_loss >= 0 ? '+' : ''}{formatMoney(summary.realized_profit_loss)}원
            </strong>
          </span>
        </div>
      )}

      {!error && (
        <section className={styles.accountSection}>
          <h4 className={styles.subheading}>전략별 배정</h4>
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
                  <span><small>투자비율</small><strong>{(strategy.invest_ratio * 100).toFixed(1)}%</strong></span>
                  <span><small>배정 한도</small><strong>{formatMoney(strategy.allocation_amount)}원</strong></span>
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
                {item.status !== 'matched' && item.strategies.length > 0 && (
                  <div className={styles.syncControls}>
                    <select
                      value={syncDrafts[item.currency]?.strategyId || ''}
                      onChange={(event) => setSyncDrafts((current) => ({
                        ...current,
                        [item.currency]: { ...current[item.currency], strategyId: event.target.value },
                      }))}
                    >
                      {item.strategies
                        .filter((strategy) => item.status === 'external_balance' || strategy.volume > 0)
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
                    <button onClick={() => applySync(item)} disabled={loading}>{item.status === 'external_balance' ? '전략에 배정' : '전략에서 차감'}</button>
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