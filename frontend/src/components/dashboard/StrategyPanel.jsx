import { useEffect, useRef, useState } from 'react'
import { Plus } from 'lucide-react'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import StrategyCard from './StrategyCard'
import SubscriptionWizard from './SubscriptionWizard'
import { MIN_ORDER_AMOUNT } from './AllocationFields'
import { coinIconForMarket } from '../../utils/coinIcons'
import panelStyles from './Panel.module.css'
import styles from './StrategyPanel.module.css'

const REFRESH_INTERVAL_MS = 5_000

export default function StrategyPanel({ executionMode = 'simulated' }) {
  const [markets, setMarkets] = useState([])
  const [strategies, setStrategies] = useState([])
  const [loadingId, setLoadingId] = useState(null)
  const [error, setError] = useState('')
  const [loadError, setLoadError] = useState('')
  const [notice, setNotice] = useState('')
  const [toast, setToast] = useState('')
  const toastTimer = useRef(null)
  const [ratioDrafts, setRatioDrafts] = useState({})
  const [amountDrafts, setAmountDrafts] = useState({})
  const [inputModeDrafts, setInputModeDrafts] = useState({})
  const [timeframeDrafts, setTimeframeDrafts] = useState({})
  const [stopLossDrafts, setStopLossDrafts] = useState({})
  const [takeProfitDrafts, setTakeProfitDrafts] = useState({})
  const [activationPrompt, setActivationPrompt] = useState({ id: null, nonce: 0 })
  const [liquidating, setLiquidating] = useState(false)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [reservedList, setReservedList] = useState([])
  const availableCash = strategies.length > 0 ? strategies[0].available_cash : null
  const visibleStrategies = strategies.filter((strategy) => strategy.selected || strategy.has_open_position)

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const showToast = (message) => {
    setToast(message)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 3_500)
  }

  const loadStrategies = () => {
    setError('')
    Promise.all([
      apiFetch(`/strategies/active?mode=${executionMode}`),
      apiFetch('/strategies/markets'),
      apiFetch(`/strategies/reserved?mode=${executionMode}`),
    ])
      .then(([items, marketItems, reserved]) => {
        setStrategies(items)
        setMarkets(marketItems)
        setReservedList(reserved)
        setLoadError('')
        setRatioDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.selected ? Math.round(item.invest_ratio * 100) : 0)]),
        ))
        setAmountDrafts((current) => Object.fromEntries(
          items.map((item) => [
            item.id,
            current[item.id] ?? (item.allocated_amount ? Math.round(item.allocated_amount) : ''),
          ]),
        ))
        setInputModeDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? item.allocation_mode ?? 'ratio']),
        ))
        setTimeframeDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.selected ? item.selected_timeframe_minutes : 0)]),
        ))
        setStopLossDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.stop_loss_rate ? item.stop_loss_rate * 100 : '')]),
        ))
        setTakeProfitDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.take_profit_rate ? item.take_profit_rate * 100 : '')]),
        ))
      })
      .catch((requestError) => setLoadError(requestError.message))
  }

  usePolling(loadStrategies, REFRESH_INTERVAL_MS, executionMode)

  const replaceStrategy = (updated) => {
    setStrategies((current) => current.map((item) => (item.id === updated.id ? updated : item)))
  }

  const buildAllocationPayload = (strategy) => {
    if (inputModeDrafts[strategy.id] === 'amount') {
      const amount = Number(amountDrafts[strategy.id])
      if (!Number.isFinite(amount) || amount < MIN_ORDER_AMOUNT) {
        showToast(`주문 금액은 최소 ${MIN_ORDER_AMOUNT.toLocaleString()}원 이상으로 입력해 주세요.`)
        return null
      }
      if (strategy.available_cash != null && amount > strategy.available_cash) {
        showToast(`주문 가능 금액 ${Math.round(strategy.available_cash).toLocaleString()}원을 초과할 수 없습니다.`)
        return null
      }
      return { invest_amount: amount }
    }

    const percent = Number(ratioDrafts[strategy.id])
    if (!Number.isFinite(percent) || percent < 1 || percent > 100) {
      showToast('투자 비율은 1%부터 100% 사이로 입력해 주세요.')
      return null
    }
    if (strategy.available_cash != null) {
      const estimated = Math.floor(strategy.available_cash * percent / 100)
      if (estimated < MIN_ORDER_AMOUNT) {
        showToast(
          `이 비율로는 주문 금액이 ${estimated.toLocaleString()}원이라 최소 주문 금액 `
          + `${MIN_ORDER_AMOUNT.toLocaleString()}원에 미치지 못합니다. 비율을 높여 주세요.`,
        )
        return null
      }
    }
    return { invest_ratio: percent / 100 }
  }

  const toggleStrategy = async (strategy) => {
    if (!strategy.selected) {
      setActivationPrompt({ id: strategy.id, nonce: Date.now() })
      showToast('분봉과 투자비율을 설정한 후에 전략 활성화가 가능합니다.')
      return
    }

    let forceDisable = false
    if (strategy.selected && strategy.has_open_position) {
      forceDisable = window.confirm(
        '이 전략으로 보유 중인 포지션이 있습니다.\n\n전략을 해제하면 이후 자동 매도 신호와 손절·익절 감시가 중단되며, 보유 자산은 그대로 남습니다.\n\n그래도 전략을 해제하시겠습니까?',
      )
      if (!forceDisable) return
    }

    setLoadingId(strategy.id)
    setError('')
    try {
      replaceStrategy(await apiFetch(`/strategies/${strategy.id}/subscription?mode=${executionMode}&market=${strategy.market}`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: !strategy.selected,
          force_disable: forceDisable,
          invest_ratio: strategy.invest_ratio,
          timeframe_minutes: strategy.selected_timeframe_minutes,
          stop_loss_rate: Number(stopLossDrafts[strategy.id]) / 100 || 0,
          take_profit_rate: Number(takeProfitDrafts[strategy.id]) / 100 || 0,
        }),
      }))
      loadStrategies()
    } catch (requestError) {
      setError(requestError.message)
      showToast(requestError.message)
    } finally {
      setLoadingId(null)
    }
  }

  const saveSettings = async (strategy) => {
    const timeframe = Number(timeframeDrafts[strategy.id])
    if (!strategy.allowed_timeframes.includes(timeframe)) {
      showToast('분봉을 선택해 주세요.')
      setActivationPrompt({ id: strategy.id, nonce: Date.now() })
      return
    }
    const allocation = buildAllocationPayload(strategy)
    if (allocation === null) return

    const stopLoss = Number(stopLossDrafts[strategy.id] || 0)
    const takeProfit = Number(takeProfitDrafts[strategy.id] || 0)
    if (stopLoss < 0 || stopLoss > 100 || takeProfit < 0 || takeProfit > 100) {
      showToast('손절률과 목표 수익률은 0% 초과 100% 이하로 입력해 주세요. 빈 값은 사용 안 함입니다.')
      return
    }

    setLoadingId(strategy.id)
    setError('')
    setNotice('')
    try {
      const updated = await apiFetch(`/strategies/${strategy.id}/subscription?mode=${executionMode}&market=${strategy.market}`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: true,
          ...allocation,
          timeframe_minutes: timeframe,
          stop_loss_rate: stopLoss / 100,
          take_profit_rate: takeProfit / 100,
        }),
      })
      replaceStrategy(updated)
      setActivationPrompt({ id: null, nonce: 0 })
      loadStrategies()
      const budgetLabel = allocation.invest_amount != null
        ? `주문 금액 ${Number(allocation.invest_amount).toLocaleString()}원`
        : `투자 비율 ${Math.round(allocation.invest_ratio * 100)}%`
      setNotice(`${strategy.name} 설정을 ${timeframe}분봉, ${budgetLabel}으로 저장했습니다.`)
    } catch (requestError) {
      setError(requestError.message)
      showToast(requestError.message)
    } finally {
      setLoadingId(null)
    }
  }

  const liquidateAll = async () => {
    const modeLabel = executionMode === 'live' ? '실제 Upbit 계좌' : '모의계좌'
    if (!window.confirm(`${modeLabel}에서 보유 중인 모든 포지션을 전량 매도하시겠습니까?\n\n종목과 전략에 상관없이, 현재 보유 중인 포지션 전부가 대상입니다.`)) return

    setLiquidating(true)
    setError('')
    setNotice('')
    try {
      const results = await apiFetch(`/strategies/liquidate-all?mode=${executionMode}`, { method: 'POST' })
      if (results.length === 0) {
        setNotice('현재 보유 중인 포지션이 없습니다.')
      } else {
        setNotice(`전량 매도 처리 완료: ${results.length}개 전략, 총 ${results.reduce((sum, item) => sum + item.execution_count, 0)}건`)
      }
      loadStrategies()
    } catch (requestError) {
      setError(requestError.message)
      showToast(requestError.message)
    } finally {
      setLiquidating(false)
    }
  }

  const cancelReservation = async (strategy) => {
    if (!window.confirm(`${strategy.name} 구독을 취소할까요?\n\n아직 매수되지 않은 예약 금액이 해제되어, 다른 전략에서 사용할 수 있게 됩니다.`)) return
    setLoadingId(strategy.id)
    setError('')
    try {
      replaceStrategy(await apiFetch(`/strategies/${strategy.id}/subscription?mode=${executionMode}&market=${strategy.market}`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: false,
          invest_ratio: strategy.invest_ratio,
        }),
      }))
      loadStrategies()
      showToast(`${strategy.name} 예약을 취소했습니다.`)
    } catch (requestError) {
      setError(requestError.message)
      showToast(requestError.message)
    } finally {
      setLoadingId(null)
    }
  }

  const manualSell = async (strategy) => {
    const modeLabel = executionMode === 'live' ? '실제 Upbit 포지션' : '모의 포지션'
    if (!window.confirm(`${strategy.name}의 ${modeLabel}을 전량 매도하시겠습니까?`)) return
    setLoadingId(strategy.id)
    setError('')
    setNotice('')
    try {
      const result = await apiFetch(`/strategies/${strategy.id}/manual-sell?mode=${executionMode}&market=${strategy.market}`, { method: 'POST' })
      setNotice(`수동 전량 매도 처리 완료: ${result.execution_count}건`)
    } catch (requestError) {
      setError(requestError.message)
      showToast(requestError.message)
    } finally {
      setLoadingId(null)
    }
  }

  const sendTestSignal = async (strategy, action) => {
    const actionLabel = action === 'buy' ? '매수' : '매도'
    if (executionMode === 'live') {
      const confirmation = action === 'buy'
        ? `${strategy.market}를 설정한 주문 예산 한도 내에서 실제 시장가 매수합니다. 계속하시겠습니까?`
        : `${strategy.market} 중 이 전략으로 매수한 수량을 실제 시장가 매도합니다. 계속하시겠습니까?`
      if (!window.confirm(confirmation)) return
    }

    setLoadingId(strategy.id)
    setError('')
    setNotice('')
    try {
      const result = await apiFetch(`/strategies/${strategy.id}/test-signal?mode=${executionMode}&market=${strategy.market}`, {
        method: 'POST',
        body: JSON.stringify({ action }),
      })
      const modeLabel = executionMode === 'live' ? '실전 테스트 신호' : '모의 신호'
      setNotice(`${actionLabel} ${modeLabel} 처리 완료: ${result.execution_count}명에게 분배됨`)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoadingId(null)
    }
  }

  const handleSubscribed = () => {
    setWizardOpen(false)
    showToast('전략을 추가했습니다. 다음 매수 신호부터 자동매매가 시작됩니다.')
    setStrategies([])
    setReservedList([])
    loadStrategies()
  }

  const strategyCard = (strategy) => (
    <StrategyCard
      key={strategy.id}
      strategy={strategy}
      executionMode={executionMode}
      loading={loadingId === strategy.id}
      ratioDraft={ratioDrafts[strategy.id] ?? ''}
      amountDraft={amountDrafts[strategy.id] ?? ''}
      inputModeDraft={inputModeDrafts[strategy.id] ?? 'ratio'}
      timeframeDraft={timeframeDrafts[strategy.id] ?? strategy.selected_timeframe_minutes}
      stopLossDraft={stopLossDrafts[strategy.id] ?? ''}
      takeProfitDraft={takeProfitDrafts[strategy.id] ?? ''}
      onRatioChange={(id, value) => setRatioDrafts((current) => ({ ...current, [id]: value }))}
      onAmountChange={(id, value) => setAmountDrafts((current) => ({ ...current, [id]: value }))}
      onInputModeChange={(id, value) => setInputModeDrafts((current) => ({ ...current, [id]: value }))}
      onTimeframeChange={(id, value) => setTimeframeDrafts((current) => ({ ...current, [id]: value }))}
      onStopLossChange={(id, value) => setStopLossDrafts((current) => ({ ...current, [id]: value }))}
      onTakeProfitChange={(id, value) => setTakeProfitDrafts((current) => ({ ...current, [id]: value }))}
      onToggle={toggleStrategy}
      onSave={saveSettings}
      onTestSignal={sendTestSignal}
      onManualSell={manualSell}
      activationPromptNonce={activationPrompt.id === strategy.id ? activationPrompt.nonce : 0}
    />
  )

  return (
    <article className={panelStyles.panel}>
      <header>
        <div><h3>자동매매 전략</h3><p>현재 사용하는 전략을 우선 표시합니다. 계산값은 5초마다 자동 갱신됩니다.</p></div>
        {!wizardOpen && (
          <button className={styles.addStrategyHeaderButton} onClick={() => setWizardOpen(true)}>
            <Plus size={16} /> 새 전략
          </button>
        )}
      </header>

      <div className={styles.content}>
        {wizardOpen ? (
          <SubscriptionWizard
            markets={markets}
            executionMode={executionMode}
            onClose={() => setWizardOpen(false)}
            onSubscribed={handleSubscribed}
          />
        ) : null}

        {reservedList.length > 0 && (
          <div className={styles.reservedSection}>
            <div className={styles.groupTitle}>
              <div><strong>예약 중인 주문</strong><span>{reservedList.length}개</span></div>
              <small>실제 전략 BUY에 아직 사용되지 않은 예약·배정 예산입니다.</small>
            </div>
            <table className={styles.reservedTable}>
              <thead>
                <tr>
                  <th>종목</th>
                  <th>전략</th>
                  <th>분봉</th>
                  <th>예약 금액</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reservedList.map((item) => (
                  <tr key={`${item.id}-${item.market}`}>
                    <td>
                      <span className={styles.reservedAsset}>
                        <span className={styles.reservedCoinIcon} aria-hidden="true">
                          <span>{item.market.split('-').at(-1).slice(0, 2)}</span>
                          <img src={coinIconForMarket(item.market)} alt="" onError={(event) => event.currentTarget.remove()} />
                        </span>
                        <span>{item.market_name}<small>{item.market}</small></span>
                      </span>
                    </td>
                    <td>{item.name}</td>
                    <td>{item.timeframe_minutes}분</td>
                    <td>
                      {item.allocated_amount != null
                        ? `${Math.round(item.allocated_amount).toLocaleString()}원`
                        : `투자 비율 ${Math.round(item.invest_ratio * 100)}%`}
                    </td>
                    <td>
                      <button
                        className={styles.cancelButton}
                        onClick={() => cancelReservation(item)}
                        disabled={loadingId === item.id}
                      >
                        {loadingId === item.id ? '처리 중...' : '예약 취소'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className={styles.groupTitle}>
          <div><strong>사용 중인 전략</strong><span>{visibleStrategies.length}개</span></div>
          <small>포지션이 남은 해제 전략도 이 영역에 표시됩니다.</small>
        </div>
        {visibleStrategies.map(strategyCard)}
        {!error && !loadError && strategies.length > 0 && visibleStrategies.length === 0 && (
          <div className={styles.noSelection}>
            <strong>아직 사용 중인 전략이 없습니다.</strong>
            <span>상단의 "새 전략" 버튼을 눌러 시작해 보세요.</span>
          </div>
        )}

        {!error && !loadError && strategies.length === 0 && <div className={panelStyles.empty}>제공 중인 전략이 없습니다.</div>}
        <details className={styles.dangerZone}>
          <summary>
            <span><strong>고급 작업</strong><small>여러 전략의 보유 포지션을 한 번에 정리합니다.</small></span>
          </summary>
          <div className={styles.dangerZoneBody}>
            <div>
              <strong>모든 전략 포지션 일괄 매도</strong>
              <p>SignalTrade 전략이 보유한 포지션만 매도합니다. 외부/미배정 자산은 포함하지 않습니다.</p>
            </div>
            <button className={styles.liquidateButton} onClick={liquidateAll} disabled={liquidating}>
              {liquidating ? '매도 처리 중...' : '보유 포지션 전량 매도'}
            </button>
          </div>
        </details>
        {loadError && <p className={styles.error}>{loadError}</p>}
        {error && <p className={styles.error}>{error}</p>}
        {notice && <p className={styles.success}>{notice}</p>}
        <p className={styles.notice}>
          주문 금액은 전략을 선택하는 시점의 주문 가능 현금을 기준으로 확정되며, 매도하면 회수한 금액이 다음 주문 예산이 됩니다.
          주문 가능 금액은 매수 수수료(약 0.05%)를 미리 뺀 값이라 100%로 설정해도 수수료 부족으로 주문이 실패하지 않습니다.
          {availableCash != null && ` 현재 주문 가능 금액은 ${Math.round(availableCash).toLocaleString()}원입니다.`}
        </p>
      </div>
      {toast && <div className={styles.toast} role="alert">{toast}</div>}
    </article>
  )
}
