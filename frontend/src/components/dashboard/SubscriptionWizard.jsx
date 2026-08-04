import { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, X } from 'lucide-react'
import { apiFetch } from '../../api/client'
import { formatNumber } from '../../utils/format'
import AllocationFields, { MIN_ORDER_AMOUNT } from './AllocationFields'
import styles from './StrategyPanel.module.css'

const STEP_LABELS = ['종목 선택', '전략 선택', '예산 설정', '확인']

/**
 * 처음 이용하는 사용자도 쉽게 따라올 수 있도록, 새 전략 구독을
 * "종목 선택 → 전략 선택 → 예산 설정 → 확인" 네 단계로 나눈 마법사입니다.
 *
 * 부모(StrategyPanel)의 편집용 draft 상태(ratioDrafts 등)와는 완전히
 * 독립적으로 동작합니다. 구독이 완료되면 onSubscribed(market)을 호출해
 * 부모가 목록을 새로 불러오도록 합니다.
 */
export default function SubscriptionWizard({ markets, executionMode, onClose, onSubscribed }) {
  const [step, setStep] = useState(1)
  const [market, setMarket] = useState(null)
  const [strategiesForMarket, setStrategiesForMarket] = useState([])
  const [loadingStrategies, setLoadingStrategies] = useState(false)
  const [selectedStrategy, setSelectedStrategy] = useState(null)
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

  const pickableStrategies = strategiesForMarket.filter((item) => !item.selected && !item.has_open_position)
  const marketLabel = markets.find((item) => item.code === market)?.display_name || market

  const chooseMarket = (code) => {
    setMarket(code)
    setStrategiesForMarket([])
    setSelectedStrategy(null)
    setStep(2)
  }

  const chooseStrategy = (strategy) => {
    setSelectedStrategy(strategy)
    setTimeframe(strategy.timeframe_minutes)
    setInputMode('ratio')
    setRatio(String(Math.round((strategy.default_invest_ratio ?? 0.2) * 100)))
    setAmount('')
    setStopLoss('')
    setTakeProfit('')
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

        {step === 2 && (
          <>
            <p className={styles.wizardStepDesc}>{marketLabel}에 적용할 전략을 선택하세요.</p>
            {loadingStrategies && <p className={styles.wizardStepDesc}>불러오는 중...</p>}
            {!loadingStrategies && pickableStrategies.length === 0 && (
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
          <button className={styles.wizardBack} onClick={() => setStep((current) => current - 1)} disabled={saving}>
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
