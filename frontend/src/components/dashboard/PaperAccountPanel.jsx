import { useState } from 'react'
import {
  Banknote,
  CalendarCheck2,
  ChartNoAxesCombined,
  Clock3,
  PieChart,
  TrendingUp,
  WalletCards,
} from 'lucide-react'
import PagedList from './PagedList'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import panelStyles from './Panel.module.css'
import styles from './PaperAccountPanel.module.css'

function SummaryCard({ icon, tone, label, value, description, valueClassName = '' }) {
  return (
    <span className={panelStyles.summaryCard}>
      <span className={`${panelStyles.summaryIcon} ${panelStyles[`summaryIcon${tone}`]}`}>{icon}</span>
      <div>
        <small>{label}</small>
        <strong className={valueClassName}>{value}</strong>
        <p>{description}</p>
      </div>
    </span>
  )
}

export default function PaperAccountPanel({ onOverviewChange, refreshToken = 0, showHeader = true }) {
  const [account, setAccount] = useState(null)
  const [ledger, setLedger] = useState([])
  const [adjustmentAmount, setAdjustmentAmount] = useState('')
  const [savingAction, setSavingAction] = useState('')
  const [error, setError] = useState('')

  const load = () => {
    return Promise.all([
      apiFetch('/paper-account'),
      apiFetch('/paper-account/ledger'),
      apiFetch('/strategies/active?mode=simulated'),
    ])
      .then(([accountData, ledgerItems, strategies]) => {
        setAccount(accountData)
        setLedger(ledgerItems)
        setError('')
        onOverviewChange?.({
          accountEquity: accountData.total_equity ?? 0,
          strategyReservedKrw: accountData.reserved_amount ?? 0,
          activeStrategies: strategies.filter((strategy) => strategy.selected).length,
          profitLoss: accountData.profit_loss ?? 0,
          updatedAt: new Date(),
        })
      })
      .catch((requestError) => setError(requestError.message))
  }

  usePolling(load, 5_000, refreshToken)

  const adjustCash = async (action) => {
    const amount = Number(adjustmentAmount)
    if (!Number.isFinite(amount) || amount <= 0) {
      setError('입출금 금액은 0원보다 크게 입력해 주세요.')
      return
    }
    setSavingAction(action)
    setError('')
    try {
      await apiFetch(`/paper-account/${action}`, {
        method: 'POST',
        body: JSON.stringify({ amount }),
      })
      setAdjustmentAmount('')
      await load()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSavingAction('')
    }
  }

  const profit = account?.profit_loss ?? 0
  const returnRate = account?.return_rate ?? 0

  return (
    <article className={panelStyles.panel}>
      {showHeader && (
        <header>
          <div><h3>모의계좌</h3><p>가상 자금과 전략 포지션을 실전투자 화면과 같은 구조로 확인합니다.</p></div>
        </header>
      )}

      <div className={panelStyles.content}>
        <div className={panelStyles.accountIntro}>
          <h3>모의계좌 요약</h3>
          <p>모의 현금, 예약 예산과 전략이 보유한 가상 포지션을 기준으로 보여드려요.</p>
        </div>

        <div className={panelStyles.summaryCards}>
          <SummaryCard icon={<WalletCards size={21} />} tone="blue" label="모의 총 평가자산" value={`${formatNumber(account?.total_equity)}원`} description="가상 현금과 보유 포지션 평가액" />
          <SummaryCard icon={<Banknote size={21} />} tone="purple" label="주문 가능 KRW" value={`${formatNumber(account?.available_for_order)}원`} description="예약 예산을 제외한 즉시 주문 가능액" />
          <SummaryCard icon={<CalendarCheck2 size={21} />} tone="green" label="미체결 전략 예약 KRW" value={`${formatNumber(account?.reserved_amount)}원`} description="아직 매수되지 않은 전략 예산" />
          <SummaryCard icon={<PieChart size={21} />} tone="orange" label="전략 보유 포지션" value={`${formatNumber(account?.holdings_value)}원`} description="현재 보유 중인 모의 포지션 평가액" />
          <SummaryCard icon={<Clock3 size={21} />} tone="sky" label="모의 현금 잔고" value={`${formatNumber(account?.cash_balance)}원`} description="예약 예산을 포함한 전체 가상 현금" />
          <SummaryCard icon={<ChartNoAxesCombined size={21} />} tone="purple" label="순입금액" value={`${formatNumber(account?.net_deposit)}원`} description="모의 입금액에서 출금액을 제외한 금액" />
          <SummaryCard icon={<TrendingUp size={21} />} tone="red" label="누적 손익" value={`${profit >= 0 ? '+' : ''}${formatNumber(profit)}원`} description="보유 포지션의 현재 평가액을 포함한 성과" valueClassName={profit >= 0 ? panelStyles.positive : panelStyles.negative} />
          <SummaryCard icon={<TrendingUp size={21} />} tone="green" label="누적 수익률" value={`${returnRate >= 0 ? '+' : ''}${returnRate.toFixed(2)}%`} description="순입금액 대비 누적 손익률" valueClassName={returnRate >= 0 ? panelStyles.positive : panelStyles.negative} />
        </div>

        <section className={`${panelStyles.accountSection} ${styles.cashSection}`}>
          <div className={panelStyles.sectionTitle}>
            <div>
              <h4>모의 자금 관리</h4>
              <p>실제 결제 없이 연습에 사용할 가상 원화를 입금하거나 출금합니다.</p>
            </div>
          </div>
          <div className={styles.adjustment}>
            <label htmlFor="paper-adjustment">처리할 금액</label>
            <div className={styles.amountField}>
              <input id="paper-adjustment" type="number" min="1" step="10000" placeholder="금액 입력" value={adjustmentAmount} onChange={(event) => setAdjustmentAmount(event.target.value)} />
              <span>원</span>
            </div>
            <button onClick={() => adjustCash('deposit')} disabled={Boolean(savingAction)}>
              {savingAction === 'deposit' ? '입금 중...' : '모의 입금'}
            </button>
            <button className={styles.withdrawButton} onClick={() => adjustCash('withdraw')} disabled={Boolean(savingAction)}>
              {savingAction === 'withdraw' ? '출금 중...' : '모의 출금'}
            </button>
          </div>
          {error && <p className={styles.error}>{error}</p>}
        </section>

        <section className={`${panelStyles.accountSection} ${styles.ledgerSection}`}>
          <div className={panelStyles.sectionTitle}>
            <div>
              <h4>모의계좌 거래 내역</h4>
              <p>가상 원화 입출금과 전략의 모의 매수·매도 결과를 확인합니다.</p>
            </div>
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
                  <span className={`${isPositive ? styles.ledgerUp : styles.ledgerDown} ${styles.ledgerBadge}`}>{kindLabel}</span>
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
                    <span className={styles.ledgerAmount}>{isSell ? '회수 ' : ''}{isPositive ? '+' : ''}{formatNumber(item.amount)}원</span>
                    <small>처리 후 {formatNumber(item.balance_after)}원</small>
                  </div>
                </div>
              )
            }}
          />
        </section>
      </div>
    </article>
  )
}
