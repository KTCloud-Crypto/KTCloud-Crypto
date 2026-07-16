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
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    setError('')
    apiFetch('/positions/balance')
      .then(setBalances)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

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
    </article>
  )
}
