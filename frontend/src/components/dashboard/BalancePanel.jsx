import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { apiFetch } from '../../api/client'
import styles from './Panel.module.css'

function formatQuantity(value) {
  if (value === 0) return '0'
  return value.toLocaleString(undefined, { maximumFractionDigits: 8 })
}

export default function BalancePanel() {
  const [balances, setBalances] = useState([])
  const [reconciliation, setReconciliation] = useState([])
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
    ])
      .then(([balanceItems, reconciliationItems]) => {
        setBalances(balanceItems)
        setReconciliation(reconciliationItems)
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

  return (
    <article className={styles.panel}>
      <header>
        <div>
          <h3>보유 잔고</h3>
          <p>Upbit 실계좌 잔고 (실시간 조회)</p>
        </div>
        <button className={styles.iconButton} onClick={load} disabled={loading} aria-label="새로고침"><RefreshCw size={18} /></button>
      </header>

      {error && <div className={styles.empty}>{error}</div>}
      {syncNotice && <div className={styles.syncNotice}>{syncNotice}</div>}

      {!error && (
        <div className={styles.scroll}>
          <table>
            <thead><tr><th>화폐</th><th>보유수량</th><th>주문중수량</th><th>평균매수가</th></tr></thead>
            <tbody>
              {balances.map((item) => (
                <tr key={item.currency}>
                  <td><strong>{item.currency}</strong></td>
                  <td>{formatQuantity(item.balance)}</td>
                  <td>{formatQuantity(item.locked)}</td>
                  <td>{formatQuantity(item.avg_buy_price)}원</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && balances.length === 0 && <div className={styles.empty}>보유 잔고가 없습니다.</div>}
        </div>
      )}

      {!error && (
        <div className={styles.scroll}>
          <table>
            <thead><tr><th>화폐</th><th>Upbit 총보유량</th><th>전략 기록 수량</th><th>차이</th><th>동기화 상태</th></tr></thead>
            <tbody>
              {reconciliation.map((item) => (
                <tr key={item.currency}>
                  <td><strong>{item.currency}</strong></td>
                  <td>{formatQuantity(item.actual_total)}</td>
                  <td>{formatQuantity(item.strategy_volume)}</td>
                  <td>{item.difference > 0 ? '+' : ''}{formatQuantity(item.difference)}</td>
                  <td>
                    <span className={item.status === 'matched' ? styles.success : item.status === 'external_balance' ? styles.neutral : styles.failed}>
                      {item.status === 'matched' ? '일치' : item.status === 'external_balance' ? '외부 보유 수량 있음' : '실제 잔고 부족'}
                    </span>
                    <small>{item.message}</small>
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && reconciliation.length === 0 && <div className={styles.empty}>비교할 코인 잔고 또는 실전 전략 포지션이 없습니다.</div>}
        </div>
      )}
    </article>
  )
}
