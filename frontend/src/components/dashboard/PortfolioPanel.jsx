import { useEffect, useState } from 'react'
import { Info, RefreshCw } from 'lucide-react'
import { apiFetch } from '../../api/client'
import styles from './Panel.module.css'

function formatMoney(value) {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function PortfolioPanel() {
  const [portfolio, setPortfolio] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    setError('')
    apiFetch('/positions/portfolio')
      .then(setPortfolio)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (error) {
    return (
      <article className={styles.panel}>
        <header>
          <div>
            <h3>포트폴리오 현황</h3>
            <p>총 운용자산과 전략별 배정 한도</p>
          </div>
        </header>
        <div className={styles.empty}>{error}</div>
      </article>
    )
  }

  if (!portfolio) return null

  return (
    <article className={styles.panel}>
      <header>
        <div>
          <h3>포트폴리오 현황</h3>
          <p>총 운용자산과 전략별 배정 한도 (실시간)</p>
        </div>
        <button className={styles.iconButton} onClick={load} disabled={loading} aria-label="새로고침">
          <RefreshCw size={18} />
        </button>
      </header>

      <div className={styles.portfolioSummary}>
        <div className={styles.summaryRow}>
          <span>현금 (KRW)</span>
          <strong>{formatMoney(portfolio.available_krw)}원</strong>
        </div>
        <div className={styles.summaryRow}>
          <span>보유 코인 평가액</span>
          <strong>{formatMoney(portfolio.managed_positions_value)}원</strong>
        </div>
        <div className={styles.summaryDivider} />
        <div className={styles.summaryRow}>
          <span>
            총 운용자산
            <span className={styles.tooltip}>
              <Info size={14} />
              <span className={styles.tooltipText}>
                현금 + 전략이 보유한 코인의 현재 평가액. 매수 신호 발생 시 이 금액을 기준으로 투자 비율이 계산됩니다.
              </span>
            </span>
          </span>
          <strong className={styles.totalEquity}>{formatMoney(portfolio.total_equity)}원</strong>
        </div>
      </div>

{portfolio.strategies.length > 0 && (
        <div className={styles.portfolioList}>
          {portfolio.strategies
            .filter((strategy) => strategy.strategy_code !== 'manual_hold_v1' || strategy.current_position_value > 0)
            .map((strategy) => (
              <div key={strategy.strategy_id + strategy.market} className={styles.portfolioCard}>
                <div className={styles.portfolioCardHeader}>
                  <span className={styles.portfolioCardName}>
                    <strong>{strategy.strategy_name}</strong>
                    <small>{strategy.market}</small>
                  </span>
                  <span className={strategy.enabled ? styles.success : styles.neutral}>
                    {strategy.enabled ? '활성' : '비활성'}
                  </span>
                </div>
                <div className={styles.portfolioCardMetrics}>
                  <span><small>투자비율</small><strong>{(strategy.invest_ratio * 100).toFixed(1)}%</strong></span>
                  <span><small>배정 한도</small><strong>{formatMoney(strategy.allocation_amount)}원</strong></span>
                  <span><small>현재 포지션</small><strong>{formatMoney(strategy.current_position_value)}원</strong></span>
                </div>
              </div>
            ))}
        </div>
      )}

      {portfolio.strategies.filter((strategy) => strategy.strategy_code !== 'manual_hold_v1' || strategy.current_position_value > 0).length === 0 && (
        <div className={styles.empty}>활성화된 실전투자 전략이 없습니다.</div>
      )}
    </article>
  )
}
