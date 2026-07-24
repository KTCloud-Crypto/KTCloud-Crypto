import { useState } from 'react'
import { ChevronDown, Clock3, LineChart, RefreshCw, Settings2 } from 'lucide-react'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import { metricEntries, parameterSummary } from '../../utils/strategyDisplay'
import styles from './StrategyPanel.module.css'

function RuntimeSummary({ strategy }) {
  if (!strategy.last_evaluated_at) {
    return <div className={styles.runtime}><span>선택한 분봉의 첫 마감 데이터를 기다리는 중입니다.</span></div>
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
  timeframeDraft,
  stopLossDraft,
  takeProfitDraft,
  onRatioChange,
  onTimeframeChange,
  onStopLossChange,
  onTakeProfitChange,
  onToggle,
  onSave,
  onTestSignal,
  onManualSell,
}) {
  const [expanded, setExpanded] = useState(false)

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
            <span>투자 비율 {Math.round(strategy.invest_ratio * 100)}%</span>
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
        <div className={styles.controls}>
          <div className={styles.settingGrid}>
            <div className={styles.ratioControl}>
              <label htmlFor={`timeframe-${strategy.id}`}>분봉 및 투자 비율</label>
              <div>
                <select
                  id={`timeframe-${strategy.id}`}
                  value={timeframeDraft}
                  onChange={(event) => onTimeframeChange(strategy.id, Number(event.target.value))}
                  disabled={loading}
                >
                  {strategy.allowed_timeframes.map((minutes) => (
                    <option key={minutes} value={minutes}>{minutes}분</option>
                  ))}
                </select>
                <input
                  aria-label={`${strategy.name} 투자 비율`}
                  type="number"
                  min="1"
                  max="100"
                  step="1"
                  value={ratioDraft}
                  onChange={(event) => onRatioChange(strategy.id, event.target.value)}
                  disabled={loading}
                />
                <span>%</span>
              </div>
              <small>전체 운용자산을 기준으로 적용할 투자 비율입니다.</small>
            </div>

            <div className={styles.exitControl}>
              <label>자동 청산 <small>빈 값은 사용하지 않음</small></label>
              <div>
                <span>손절</span>
                <input type="number" min="0.1" max="100" step="0.1" value={stopLossDraft} onChange={(event) => onStopLossChange(strategy.id, event.target.value)} disabled={loading} placeholder="미사용" />
                <b>%</b>
                <span>익절</span>
                <input type="number" min="0.1" max="100" step="0.1" value={takeProfitDraft} onChange={(event) => onTakeProfitChange(strategy.id, event.target.value)} disabled={loading} placeholder="미사용" />
                <b>%</b>
              </div>
              <small>보유 포지션의 평균 매수가를 기준으로 자동 매도합니다.</small>
            </div>
          </div>

          <div className={styles.actionBar}>
            {strategy.selected && <button className={styles.saveButton} onClick={() => onSave(strategy)} disabled={loading}>변경사항 저장</button>}
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
