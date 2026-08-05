import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, ChevronDown, Layers3, Sparkles, X } from 'lucide-react'
import { apiFetch } from '../../api/client'
import { formatNumber } from '../../utils/format'
import AllocationFields, { MIN_ORDER_AMOUNT } from './AllocationFields'
import { RECOMMENDED_PRESETS } from './recommendedPresets'
import styles from './StrategyPanel.module.css'

const STEP_LABELS = ['종목 선택', '전략 선택', '예산 설정', '확인']

export default function SubscriptionWizard({ markets, executionMode, onClose, onSubscribed }) {
  const [step, setStep] = useState(1)
  const [market, setMarket] = useState(null)
  const [strategiesForMarket, setStrategiesForMarket] = useState([])
  const [loadingStrategies, setLoadingStrategies] = useState(false)
  const [pickMode, setPickMode] = useState(null)
  const [expandedPresetId, setExpandedPresetId] = useState(null)
  const [selectedStrategy, setSelectedStrategy] = useState(null)
  const [activePreset, setActivePreset] = useState(null)
  const [timeframe, setTimeframe] = useState(0)
  const [inputMode, setInputMode] = useState('ratio')
  const [ratio, setRatio] = useState('20')
  const [amount, setAmount] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!market) return
    setLoadingStrategies(true)
    setError('')
    apiFetch(`/strategies?mode=${executionMode}&market=${market}`)
      .then(setStrategiesForMarket)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoadingStrategies(false))
  }, [market, executionMode])

  const recommendedCodes = new Set(RECOMMENDED_PRESETS.map((preset) => preset.strategyCode))
  const pickableStrategies = strategiesForMarket.filter((item) => (
    !item.selected && !item.has_open_position && !recommendedCodes.has(item.code)
  ))
  const marketLabel = markets.find((item) => item.code === market)?.display_name || market

  const chooseMarket = (code) => {
    setMarket(code)
    setStrategiesForMarket([])
    setPickMode(null)
    setExpandedPresetId(null)
    setSelectedStrategy(null)
    setActivePreset(null)
    setStep(2)
  }

  const chooseStrategy = (strategy) => {
    setSelectedStrategy(strategy)
    setActivePreset(null)
    setTimeframe(strategy.timeframe_minutes)
    setInputMode('ratio')
    setRatio(String(Math.round((strategy.default_invest_ratio ?? 0.2) * 100)))
    setAmount('')
    setStopLoss('')
    setTakeProfit('')
    setError('')
    setStep(3)
  }

  const chooseRecommended = (preset) => {
    const strategy = strategiesForMarket.find((item) => item.code === preset.strategyCode)
    if (!strategy || strategy.selected || strategy.has_open_position) {
      setError(`${preset.label}은(는) 이미 이 종목에서 사용 중입니다.`)
      return
    }
    setSelectedStrategy(strategy)
    setActivePreset(preset)
    setTimeframe(preset.timeframe)
    setInputMode('ratio')
    setRatio(String(preset.defaultRatio))
    setAmount('')
    setStopLoss(String(preset.stopLoss))
    setTakeProfit(String(preset.takeProfit))
    setError('')
    setStep(3)
  }

  const ratioPercent = Number(ratio)
  const estimatedAmount = (
    inputMode === 'ratio'
    && selectedStrategy?.available_cash != null
    && Number.isFinite(ratioPercent)
    && ratioPercent > 0
  )
    ? Math.floor(selectedStrategy.available_cash * ratioPercent / 100)
    : null

  const canProceedToConfirm = Boolean(selectedStrategy)
    && timeframe > 0
    && (
      inputMode === 'amount'
        ? Number(amount) >= MIN_ORDER_AMOUNT
        : Number.isFinite(ratioPercent) && ratioPercent >= 1 && ratioPercent <= 100
          && (estimatedAmount == null || estimatedAmount >= MIN_ORDER_AMOUNT)
    )

  const budgetLabel = inputMode === 'amount'
    ? `${Number(amount || 0).toLocaleString()}원`
    : `${ratioPercent || 0}% (약 ${formatNumber(estimatedAmount ?? 0)}원)`

  const handleSubmit = async () => {
    if (!selectedStrategy) return
    setSaving(true)
    setError('')
    try {
      const payload = {
        enabled: true,
        timeframe_minutes: Number(timeframe),
        stop_loss_rate: Number(stopLoss || 0) / 100,
        take_profit_rate: Number(takeProfit || 0) / 100,
        ...(inputMode === 'amount'
          ? { invest_amount: Number(amount) }
          : { invest_ratio: ratioPercent / 100 }),
      }
      await apiFetch(`/strategies/${selectedStrategy.id}/subscription?mode=${executionMode}&market=${market}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      onSubscribed(market)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.wizardCard}>
      <div className={styles.wizardHeader}>
        <div className={styles.wizardSteps}>
          {STEP_LABELS.map((label, index) => {
            const stepNumber = index + 1
            const state = stepNumber === step ? styles.wizardStepActive : stepNumber < step ? styles.wizardStepDone : ''
            return (
              <span key={label} className={`${styles.wizardStepItem} ${state}`}>
                <b>{stepNumber < step ? <CheckCircle2 size={13} /> : stepNumber}</b>
                {label}
              </span>
            )
          })}
        </div>
        <button className={styles.wizardClose} onClick={onClose} aria-label="새 전략 추가 취소">
          <X size={18} />
        </button>
      </div>

      <div className={styles.wizardBody}>
        {step === 1 && (
          <>
            <p className={styles.wizardStepDesc}>자동매매를 적용할 종목을 선택하세요.</p>
            <div className={styles.marketGrid}>
              {markets.map((item) => (
                <button key={item.code} className={styles.marketOption} onClick={() => chooseMarket(item.code)}>
                  <strong>{item.display_name}</strong>
                  <small>{item.code}</small>
                </button>
              ))}
            </div>
          </>
        )}

        {step === 2 && loadingStrategies && <p className={styles.wizardStepDesc}>불러오는 중...</p>}

        {step === 2 && !loadingStrategies && pickMode === null && (
          <>
            <p className={styles.wizardStepDesc}>{marketLabel}에 적용할 방식을 선택하세요.</p>
            <div className={styles.modeChoiceGrid}>
              <button type="button" className={styles.modeChoiceTile} onClick={() => setPickMode('recommended')}>
                <span className={styles.modeChoiceIcon}><Sparkles size={22} /></span>
                <strong>추천 전략</strong>
                <small>초보자에게 추천하는 3가지 세팅 중 골라서 투자 비율만 정하면 바로 시작할 수 있어요.</small>
              </button>
              <button type="button" className={styles.modeChoiceTile} onClick={() => setPickMode('custom')}>
                <span className={styles.modeChoiceIcon}><Layers3 size={22} /></span>
                <strong>직접 설정</strong>
                <small>전략과 분봉, 손절·익절까지 원하는 대로 하나씩 직접 정해요.</small>
              </button>
            </div>
          </>
        )}

        {step === 2 && !loadingStrategies && pickMode === 'recommended' && (
          <>
            <p className={styles.wizardStepDesc}>
              카드를 눌러 자세한 설명을 확인하고, 마음에 드는 세팅으로 시작하세요.
            </p>
            <div className={styles.presetAccordion}>
              {RECOMMENDED_PRESETS.map((preset) => {
                const strategy = strategiesForMarket.find((item) => item.code === preset.strategyCode)
                const unavailable = !strategy || strategy.selected || strategy.has_open_position
                const expanded = expandedPresetId === preset.id
                return (
                  <div key={preset.id} className={`${styles.presetItem} ${expanded ? styles.presetItemOpen : ''}`}>
                    <button
                      type="button"
                      className={styles.presetItemHeader}
                      onClick={() => setExpandedPresetId(expanded ? null : preset.id)}
                      aria-expanded={expanded}
                    >
                      <span className={styles.presetBadge}>추천</span>
                      <span className={styles.presetItemHeaderText}>
                        <strong>{preset.label}</strong>
                        <small>{preset.description}</small>
                      </span>
                      <ChevronDown className={expanded ? styles.chevronOpen : ''} size={18} />
                    </button>

                    {expanded && (
                      <div className={styles.presetItemBody}>
                        <p>{preset.detail}</p>
                        <div className={styles.presetFixedInfo}>
                          <span><small>분봉</small><strong>{preset.timeframe}분</strong></span>
                          <span><small>손절</small><strong>-{preset.stopLoss}%</strong></span>
                          <span><small>익절</small><strong>+{preset.takeProfit}%</strong></span>
                        </div>
                        {unavailable ? (
                          <p className={styles.presetUnavailable}>이미 이 종목에서 사용 중인 전략이에요.</p>
                        ) : (
                          <button type="button" className={styles.presetStartButton} onClick={() => chooseRecommended(preset)}>
                            이 세팅으로 시작하기 <ArrowRight size={14} />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        )}

        {step === 2 && !loadingStrategies && pickMode === 'custom' && (
          <>
            <p className={styles.wizardStepDesc}>{marketLabel}에 적용할 전략을 선택하세요.</p>
            {pickableStrategies.length === 0 && (
              <p className={styles.wizardStepDesc}>이 종목에는 추가로 선택할 수 있는 전략이 없습니다. 이미 모든 전략을 사용 중입니다.</p>
            )}
            <div className={styles.strategyList}>
              {pickableStrategies.map((strategy) => (
                <button key={strategy.id} className={styles.strategyOption} onClick={() => chooseStrategy(strategy)}>
                  <span>
                    <strong>{strategy.name}</strong>
                    <small>{strategy.description}</small>
                  </span>
                  <ArrowRight size={16} />
                </button>
              ))}
            </div>
          </>
        )}

        {step === 3 && selectedStrategy && (
          <>
            <p className={styles.wizardStepDesc}>{marketLabel} · {selectedStrategy.name}의 매수 조건을 설정하세요.</p>

            {activePreset ? (
              <div className={styles.presetBudget}>
                <div className={styles.presetFixedInfo}>
                  <span><small>분봉</small><strong>{activePreset.timeframe}분</strong></span>
                  <span><small>손절</small><strong>-{activePreset.stopLoss}%</strong></span>
                  <span><small>익절</small><strong>+{activePreset.takeProfit}%</strong></span>
                </div>
                <label htmlFor="preset-ratio" className={styles.presetRatioLabel}>투자 비율</label>
                <div className={styles.presetRatioRow}>
                  <input
                    id="preset-ratio"
                    type="number"
                    min="1"
                    max="100"
                    step="1"
                    value={ratio}
                    onChange={(event) => setRatio(event.target.value)}
                  />
                  <span>%</span>
                  {estimatedAmount != null && (
                    <em className={estimatedAmount < MIN_ORDER_AMOUNT ? styles.presetEstimateWarning : styles.presetEstimate}>
                      ≈ {formatNumber(estimatedAmount)}원
                    </em>
                  )}
                </div>
                <p className={styles.presetHint}>
                  주문 가능 금액에서 이 비율만큼 매수합니다. 최소 주문 금액은 {MIN_ORDER_AMOUNT.toLocaleString()}원입니다.
                </p>
              </div>
            ) : (
              <AllocationFields
                strategy={selectedStrategy}
                timeframe={timeframe}
                inputMode={inputMode}
                ratio={ratio}
                amount={amount}
                stopLoss={stopLoss}
                takeProfit={takeProfit}
                loading={saving}
                onTimeframeChange={setTimeframe}
                onInputModeChange={setInputMode}
                onRatioChange={setRatio}
                onAmountChange={setAmount}
                onStopLossChange={setStopLoss}
                onTakeProfitChange={setTakeProfit}
              />
            )}
          </>
        )}

        {step === 4 && selectedStrategy && (
          <>
            <p className={styles.wizardStepDesc}>아래 내용으로 자동매매를 시작합니다.</p>
            <div className={styles.wizardSummary}>
              <div className={styles.summaryRow}><small>종목</small><strong>{marketLabel} ({market})</strong></div>
              <div className={styles.summaryRow}><small>전략</small><strong>{selectedStrategy.name}</strong></div>
              <div className={styles.summaryRow}><small>분봉</small><strong>{timeframe}분</strong></div>
              <div className={styles.summaryRow}><small>주문 예산</small><strong>{budgetLabel}</strong></div>
              {stopLoss && <div className={styles.summaryRow}><small>손절</small><strong>{stopLoss}%</strong></div>}
              {takeProfit && <div className={styles.summaryRow}><small>익절</small><strong>{takeProfit}%</strong></div>}
            </div>
          </>
        )}

        {error && <p className={styles.wizardError}>{error}</p>}
      </div>

      <div className={styles.wizardActions}>
{step > 1 && (
          <button
            className={styles.wizardBack}
            onClick={() => {
              if (step === 2 && pickMode !== null) {
                setPickMode(null)
              } else {
                setStep((current) => current - 1)
              }
            }}
            disabled={saving}
          >
            <ArrowLeft size={15} /> 이전
          </button>
        )}
        {step === 3 && (
          <button className={styles.wizardNext} onClick={() => setStep(4)} disabled={!canProceedToConfirm}>
            다음 <ArrowRight size={15} />
          </button>
        )}
        {step === 4 && (
          <button className={styles.wizardNext} onClick={handleSubmit} disabled={saving}>
            {saving ? '시작하는 중...' : '자동매매 시작하기'}
          </button>
        )}
      </div>
    </div>
  )
}