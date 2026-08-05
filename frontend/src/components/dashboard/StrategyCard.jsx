import { useEffect, useState } from 'react'
import { ChevronDown, Clock3, Hourglass, LineChart, RefreshCw, Settings2 } from 'lucide-react'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import { metricEntries, parameterSummary } from '../../utils/strategyDisplay'
import AllocationFields from './AllocationFields'
import styles from './StrategyPanel.module.css'

function RuntimeSummary({ strategy }) {
  if (!strategy.last_evaluated_at) {
    return (
      <div className={styles.runtimeWaiting}>
        <Hourglass size={18} />
        <span>
          <strong>첫 계산을 준비하고 있어요</strong>
          <small>{strategy.selected_timeframe_minutes}분봉 데이터가 처음 마감되면 자동으로 판정이 시작됩니다.</small>
        </span>
      </div>
    )
  }

  const actionLabel = strategy.last_action === 'buy'
    ? '매수'
    : strategy.last_action === 'sell' ? '매도' : '신호 없음'
  const metrics = metricEntries(strategy.code, strategy.last_metrics)

  return (
    <div className={styles.runtime}>
      <span><small>최근 종가</small><strong>{formatNumber(strategy.last_close_price)}원</strong></span>
      {metrics.map((metric) => (
        <span key={metric.key}><small>{metric.label}</small><strong>{formatNumber(metric.value, 2)}</strong></span>
      ))}
      <span><small>판정</small><strong>{actionLabel}</strong></span>
      <span className={styles.runtimeTime}><small>계산 시각</small><strong>{formatUtcDateTime(strategy.last_evaluated_at)}</strong></span>
    </div>
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

  useEffect(() => {
    if (activationPromptNonce) setExpanded(true)
  }, [activationPromptNonce])

  return (
    <section className={`${styles.card} ${strategy.selected ? styles.selected : ''}`}>
      <div className={styles.cardMain}>
        <div className={styles.icon}><LineChart size={22} /></div>
        <div className={styles.body}>
          <div className={styles.title}>
            <div><h4>{strategy.name}</h4><span>{strategy.code}</span></div>
            <button
              className={strategy.selected ? `${styles.selectedButton} ${strategy.paused ? styles.pausedButton : ''}` : styles.selectButton}
              onClick={() => onToggle(strategy)}
              disabled={loading}
              title={strategy.selected ? '클릭하여 전략 해제' : '전략 선택'}
            >
              {strategy.selected && !strategy.paused && <RefreshCw className={styles.runningIcon} size={21} />}
              {loading ? '처리 중...' : strategy.selected ? strategy.paused ? '신규 매수 일시정지' : '자동매매 실행 중' : '전략 선택'}
            </button>
          </div>
          <p>{strategy.description}</p>
          <div className={styles.meta}>
            <span>{strategy.market}</span>
            <span><Clock3 size={14} /> {strategy.selected_timeframe_minutes}분봉</span>
            <span>{parameterSummary(strategy)}</span>
            {strategy.selected && strategy.allocated_amount != null
              ? <span>주문 예산 {formatNumber(strategy.allocated_amount)}원</span>
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
        설정 및 테스트
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