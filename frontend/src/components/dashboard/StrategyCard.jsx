import { useEffect, useState } from 'react'
import { ChevronDown, RefreshCw, Settings2 } from 'lucide-react'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import { coinIconForMarket } from '../../utils/coinIcons'
import { parameterSummary } from '../../utils/strategyDisplay'
import AllocationFields from './AllocationFields'
import styles from './StrategyPanel.module.css'

function RuntimeSummary({ strategy }) {
  if (!strategy.last_evaluated_at) {
    return (
      <p className={styles.runtimeStatus}>첫 {strategy.selected_timeframe_minutes}분봉 마감 후 계산을 시작합니다.</p>
    )
  }

  return (
    <p className={styles.runtimeStatus}>최근 계산 {formatUtcDateTime(strategy.last_evaluated_at)}</p>
  )
}

export default function StrategyCard({
  strategy,
  executionMode,
  loading,
  ratioDraft,
  amountDraft,
  inputModeDraft,
  timeframeDraft,
  stopLossDraft,
  takeProfitDraft,
  onRatioChange,
  onAmountChange,
  onInputModeChange,
  onTimeframeChange,
  onStopLossChange,
  onTakeProfitChange,
  onToggle,
  onSave,
  onTestSignal,
  onManualSell,
  activationPromptNonce,
}) {
  const [expanded, setExpanded] = useState(false)
  const symbol = strategy.market.split('-').at(-1)
  const coinIcon = coinIconForMarket(strategy.market)

  useEffect(() => {
    if (activationPromptNonce) setExpanded(true)
  }, [activationPromptNonce])

  return (
    <section className={`${styles.card} ${strategy.selected ? styles.selected : ''}`}>
      <div className={styles.cardMain}>
        <div className={styles.body}>
          <div className={styles.title}>
            <div className={styles.strategyIdentity}>
              <span className={styles.strategyCoinIcon} aria-hidden="true">
                <span>{symbol.slice(0, 2)}</span>
                <img src={coinIcon} alt="" onError={(event) => event.currentTarget.remove()} />
              </span>
              <div>
                <h4>{strategy.name}</h4>
                <span className={styles.strategyMarket}>{symbol}/KRW · {strategy.selected_timeframe_minutes}분봉</span>
              </div>
            </div>
            <button
              className={strategy.selected ? `${styles.selectedButton} ${strategy.paused ? styles.pausedButton : ''}` : styles.selectButton}
              onClick={() => onToggle(strategy)}
              disabled={loading}
              title={strategy.selected ? '클릭하여 전략 해제' : '전략 선택'}
            >
              {strategy.selected && !strategy.paused && <RefreshCw className={styles.runningIcon} size={21} />}
              {loading ? '처리 중...' : strategy.selected ? strategy.paused ? '매수 일시정지' : '실행 중' : '전략 선택'}
            </button>
          </div>
          <p>{strategy.description}</p>
          <div className={styles.meta}>
            <span>{parameterSummary(strategy)}</span>
            {strategy.selected && strategy.allocated_amount != null
              ? <span>{strategy.allocation_mode === 'amount' ? '지정 금액' : '주문 예산'} {formatNumber(strategy.allocated_amount)}원</span>
              : <span>투자 비율 {Math.round(strategy.invest_ratio * 100)}%</span>}
            {!strategy.selected && strategy.has_open_position && <span className={styles.orphaned}>전략 해제됨 · 포지션 보유 중</span>}
          </div>
          {strategy.selected && <RuntimeSummary strategy={strategy} />}
        </div>
      </div>

      <button
        className={styles.expandButton}
        onClick={() => setExpanded((current) => !current)}
        aria-expanded={expanded}
      >
        <Settings2 size={16} />
        전략 설정
        <ChevronDown className={expanded ? styles.chevronOpen : ''} size={17} />
      </button>

      {expanded && (
        <div
          key={`${strategy.id}-${activationPromptNonce}`}
          className={`${styles.controls} ${activationPromptNonce ? styles.activationPrompt : ''}`}
        >
          <AllocationFields
            strategy={strategy}
            timeframe={timeframeDraft}
            inputMode={inputModeDraft}
            ratio={ratioDraft}
            amount={amountDraft}
            stopLoss={stopLossDraft}
            takeProfit={takeProfitDraft}
            loading={loading}
            onTimeframeChange={(value) => onTimeframeChange(strategy.id, value)}
            onInputModeChange={(value) => onInputModeChange(strategy.id, value)}
            onRatioChange={(value) => onRatioChange(strategy.id, value)}
            onAmountChange={(value) => onAmountChange(strategy.id, value)}
            onStopLossChange={(value) => onStopLossChange(strategy.id, value)}
            onTakeProfitChange={(value) => onTakeProfitChange(strategy.id, value)}
          />

          <div className={styles.actionBar}>
            <button className={styles.saveButton} onClick={() => onSave(strategy)} disabled={loading}>
              {strategy.selected ? '변경사항 저장' : '설정 저장 및 전략 활성화'}
            </button>
            {strategy.selected && executionMode === 'simulated' && (
              <div className={styles.testSignalArea}>
                <small>전략 조건이 충족됐다고 가정해 테스트 신호를 전송합니다. 이후 주문 처리는 실제 자동매매와 동일합니다.</small>
                <div className={styles.testButtons}>
                  <button onClick={() => onTestSignal(strategy, 'buy')} disabled={loading}>
                    매수 신호 전송
                  </button>
                  <button onClick={() => onTestSignal(strategy, 'sell')} disabled={loading}>
                    매도 신호 전송
                  </button>
                </div>
              </div>
            )}
            {strategy.has_open_position && <button className={styles.manualSell} onClick={() => onManualSell(strategy)} disabled={loading}>포지션 전량 매도</button>}
          </div>
        </div>
      )}
    </section>
  )
}
