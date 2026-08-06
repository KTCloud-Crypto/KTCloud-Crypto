import PagedList from './PagedList'
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
  const reserved = account?.reserved_amount ?? 0

  return (
    <article className={panelStyles.panel}>
      <header>
        <div><h3>모의계좌</h3><p>원하는 금액을 입력해 모의 투자금을 입금하거나 보유 현금에서 출금합니다.</p></div>
      </header>
      <div className={styles.content}>
        <div className={styles.summary}>
          <span>
            <small>주문 가능 현금</small>
            <strong>{formatNumber(account?.available_for_order)}원</strong>
            {reserved > 0 && (
              <em className={styles.subNote}>
                전체 {formatNumber(account?.cash_balance)}원 중 {formatNumber(reserved)}원 예약됨
              </em>
            )}
          </span>
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

<PagedList
        items={ledger}
        emptyLabel="거래 내역이 없습니다."
        renderItem={(item) => {
          const kindLabel = ({ deposit: '입금', withdraw: '출금', buy: '모의 매수', sell: '모의 매도' })[item.kind] ?? item.kind
          const isPositive = item.amount > 0
          const isSell = item.kind === 'sell'
          const profitLoss = item.realized_profit_loss
          return (
            <div key={item.id} className={styles.ledgerCard}>
                <span className={`${isPositive ? styles.ledgerUp : styles.ledgerDown} ${styles.ledgerBadge}`}>
                  {kindLabel}
                </span>
                <div className={styles.ledgerMain}>
                  {isSell && profitLoss != null ? (
                    <strong className={profitLoss >= 0 ? styles.ledgerUp : styles.ledgerDown}>
                      손익 {profitLoss >= 0 ? '+' : ''}{formatNumber(profitLoss)}원
                    </strong>
                  ) : (
                    <strong className={styles.ledgerNeutral}>{kindLabel}</strong>
                  )}
                  <small>{formatUtcDateTime(item.created_at)}</small>
                </div>
                <div className={styles.ledgerRight}>
                  <span className={styles.ledgerAmount}>
                    {isSell ? '회수 ' : ''}{isPositive ? '+' : ''}{formatNumber(item.amount)}원
                  </span>
                  <small>처리 후 {formatNumber(item.balance_after)}원</small>
                </div>
              </div>
          )
        }}
      />
    </article>
  )
}
