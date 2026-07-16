import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import styles from './Panel.module.css'

export default function TradesPanel() {
  const [trades, setTrades] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/trades')
      .then(setTrades)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <article className={styles.panel}>
      <header>
        <div>
          <h3>거래 내역</h3>
          <p>최근 200건</p>
        </div>
      </header>

      {error && <div className={styles.empty}>{error}</div>}

      {!error && (
        <div className={styles.scroll}>
          <table>
            <thead><tr><th>종목</th><th>구분</th><th>체결가</th><th>수량</th><th>상태</th><th>시각</th></tr></thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={trade.id}>
                  <td><strong>{trade.ticker}</strong></td>
                  <td><span className={trade.action === 'buy' ? styles.buy : styles.sell}>{trade.action === 'buy' ? '매수' : '매도'}</span></td>
                  <td>{trade.price ? `${trade.price.toLocaleString()}원` : '-'}</td>
                  <td>{trade.volume ?? '-'}</td>
                  <td><span className={trade.status === 'success' ? styles.success : styles.failed}>{trade.status === 'success' ? '성공' : '실패'}</span></td>
                  <td>{new Date(trade.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {trades.length === 0 && <div className={styles.empty}>거래 내역이 없습니다.</div>}
        </div>
      )}
    </article>
  )
}
