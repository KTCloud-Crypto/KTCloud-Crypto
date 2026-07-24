import { useState } from 'react'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import panelStyles from './Panel.module.css'
import styles from './PaperAccountPanel.module.css'

export default function PaperAccountPanel() {
  const [account, setAccount] = useState(null)
  const [ledger, setLedger] = useState([])
  const [adjustmentAmount, setAdjustmentAmount] = useState('')
  const [savingAction, setSavingAction] = useState('')
  const [error, setError] = useState('')

  const load = () => {
    Promise.all([apiFetch('/paper-account'), apiFetch('/paper-account/ledger')])
      .then(([accountData, ledgerItems]) => {
        setAccount(accountData)
        setLedger(ledgerItems)
        setError('')
      })
      .catch((requestError) => setError(requestError.message))
  }

  usePolling(load, 5_000)

  const adjustCash = async (action) => {
    const amount = Number(adjustmentAmount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('입출금 금액은 0원보다 크게 입력해 주세요.')
      return
    }
    setSavingAction(action)
    setError('')
    try {
      setAccount(await apiFetch(`/paper-account/${action}`, {
        method: 'POST',
        body: JSON.stringify({ amount }),
      }))
      const ledgerItems = await apiFetch('/paper-account/ledger')
      setLedger(ledgerItems)
      setAdjustmentAmount('')
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSavingAction('')
    }
  }

  const profit = account?.profit_loss ?? 0

  return (
    <article className={panelStyles.panel}>
      <header>
        <div><h3>모의계좌</h3><p>원하는 금액을 입력해 모의 투자금을 입금하거나 가용 현금에서 출금합니다.</p></div>
      </header>
      <div className={styles.content}>
        <div className={styles.summary}>
          <span><small>가용 현금</small><strong>{formatNumber(account?.cash_balance)}원</strong></span>
          <span><small>보유 평가액</small><strong>{formatNumber(account?.holdings_value)}원</strong></span>
          <span><small>총 평가금액</small><strong>{formatNumber(account?.total_equity)}원</strong></span>
          <span><small>순입금액</small><strong>{formatNumber(account?.net_deposit)}원</strong></span>
          <span className={profit >= 0 ? styles.profit : styles.loss}>
            <small>총 손익</small>
            <strong>{profit >= 0 ? '+' : ''}{formatNumber(profit)}원 ({account?.return_rate == null ? '-' : `${account.return_rate.toFixed(2)}%`})</strong>
          </span>
        </div>
        <div className={styles.adjustment}>
          <label htmlFor="paper-adjustment">처리할 금액</label>
          <input id="paper-adjustment" type="number" min="1" step="10000" placeholder="금액 입력" value={adjustmentAmount} onChange={(event) => setAdjustmentAmount(event.target.value)} />
          <span>원</span>
          <button onClick={() => adjustCash('deposit')} disabled={Boolean(savingAction)}>
            {savingAction === 'deposit' ? '입금 중...' : '입금'}
          </button>
          <button className={styles.withdrawButton} onClick={() => adjustCash('withdraw')} disabled={Boolean(savingAction)}>
            {savingAction === 'withdraw' ? '출금 중...' : '출금'}
          </button>
        </div>
        {error && <p className={styles.error}>{error}</p>}
      </div>

      {ledger.length > 0 && (
        <div className={panelStyles.scroll}>
          <table>
            <thead><tr><th>구분</th><th>변동금액</th><th>처리 후 현금</th><th>시각</th></tr></thead>
            <tbody>
              {ledger.slice(0, 10).map((item) => (
                <tr key={item.id}>
                  <td>{({ deposit: '입금', withdraw: '출금', buy: '모의 매수', sell: '모의 매도' })[item.kind] ?? item.kind}</td>
                  <td>{item.amount > 0 ? '+' : ''}{formatNumber(item.amount)}원</td>
                  <td>{formatNumber(item.balance_after)}원</td>
                  <td>{formatUtcDateTime(item.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  )
}
