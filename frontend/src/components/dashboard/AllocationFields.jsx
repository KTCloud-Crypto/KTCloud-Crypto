import { formatNumber } from '../../utils/format'
import styles from './StrategyPanel.module.css'

export const MIN_ORDER_AMOUNT = 5_000

/**
 * 분봉, 주문 금액(비율/금액), 자동 청산 조건을 입력받는 공용 영역입니다.
 * 이미 구독 중인 전략의 설정 변경(StrategyCard)과 신규 구독 마법사
 * (SubscriptionWizard) 양쪽에서 함께 사용합니다.
 *
 * 값과 변경 콜백은 항상 "id 없는 단일 값" 형태로 주고받습니다. StrategyCard처럼
 * 전략 id별로 값을 관리해야 하는 쪽에서는, 콜백을 (value) => onXChange(id, value)
 * 형태로 감싸서 넘기면 됩니다.
 */
export default function AllocationFields({
  strategy,
  timeframe,
  inputMode,
  ratio,
  amount,
  stopLoss,
  takeProfit,
  loading,
  onTimeframeChange,
  onInputModeChange,
  onRatioChange,
  onAmountChange,
  onStopLossChange,
  onTakeProfitChange,
}) {
  const isAmountMode = inputMode === 'amount'
  const ratioPercent = Number(ratio)
  const estimatedAmount = (
    !isAmountMode
    && strategy.available_cash != null
    && Number.isFinite(ratioPercent)
    && ratioPercent > 0
  )
    ? Math.floor(strategy.available_cash * ratioPercent / 100)
    : null
  const belowMinimum = estimatedAmount != null && estimatedAmount < MIN_ORDER_AMOUNT

  return (
    <div className={styles.settingGrid}>
      <div className={styles.ratioControl}>
        <label htmlFor={`timeframe-${strategy.id}`}>분봉 및 주문 금액</label>
        <div>
          <select
            id={`timeframe-${strategy.id}`}
            value={timeframe}
            onChange={(event) => onTimeframeChange(Number(event.target.value))}
            disabled={loading}
          >
            <option value={0} disabled>분봉 선택</option>
            {strategy.allowed_timeframes.map((minutes) => (
              <option key={minutes} value={minutes}>{minutes}분</option>
            ))}
          </select>
          <select
            aria-label={`${strategy.name} 입력 방식`}
            value={inputMode}
            onChange={(event) => onInputModeChange(event.target.value)}
            disabled={loading}
          >
            <option value="ratio">비율</option>
            <option value="amount">금액</option>
          </select>
          {isAmountMode ? (
            <>
              <input
                aria-label={`${strategy.name} 주문 금액`}
                type="number"
                min="5000"
                step="1000"
                value={amount}
                onChange={(event) => onAmountChange(event.target.value)}
                disabled={loading}
                placeholder="5000"
              />
              <span>원</span>
            </>
          ) : (
            <>
              <input
                aria-label={`${strategy.name} 투자 비율`}
                type="number"
                min="1"
                max="100"
                step="1"
                value={ratio}
                onChange={(event) => onRatioChange(event.target.value)}
                disabled={loading}
              />
              <span>%</span>
              {estimatedAmount != null && (
                <em className={belowMinimum ? styles.estimateWarning : styles.estimate}>
                  ≈ {formatNumber(estimatedAmount)}원
                </em>
              )}
            </>
          )}
        </div>
        <small>
          {isAmountMode
            ? `이 전략이 한 번에 주문할 금액입니다. 최소 ${MIN_ORDER_AMOUNT.toLocaleString()}원 이상이어야 합니다.`
            : '주문 가능 금액에서 이 비율만큼 주문 금액을 정합니다.'}
          {strategy.available_cash != null && ` 주문 가능 금액 ${formatNumber(strategy.available_cash)}원.`}
        </small>
        <small className={styles.feeNote}>
          주문 가능 금액은 매수 수수료(약 0.05%)를 미리 뺀 값입니다. 100%로 설정해도
          수수료만큼 여유가 남아 주문이 실패하지 않습니다.
        </small>
        {belowMinimum && (
          <small className={styles.estimateWarning}>
            예상 주문 금액이 최소 주문 금액 {MIN_ORDER_AMOUNT.toLocaleString()}원보다 작습니다. 비율을 높여 주세요.
          </small>
        )}
      </div>

      <div className={styles.exitControl}>
        <label>자동 청산 <small>빈 값은 사용하지 않음</small></label>
        <div>
          <span>손절</span>
          <input type="number" min="0.1" max="100" step="0.1" value={stopLoss} onChange={(event) => onStopLossChange(event.target.value)} disabled={loading} placeholder="미사용" />
          <b>%</b>
          <span>익절</span>
          <input type="number" min="0.1" max="100" step="0.1" value={takeProfit} onChange={(event) => onTakeProfitChange(event.target.value)} disabled={loading} placeholder="미사용" />
          <b>%</b>
        </div>
        <small>보유 포지션의 평균 매수가를 기준으로 자동 매도합니다.</small>
      </div>
    </div>
  )
}
