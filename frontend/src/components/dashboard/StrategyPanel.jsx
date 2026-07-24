import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Layers3 } from 'lucide-react'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import StrategyCard from './StrategyCard'
import panelStyles from './Panel.module.css'
import styles from './StrategyPanel.module.css'

const REFRESH_INTERVAL_MS = 5_000

export default function StrategyPanel({ executionMode = 'simulated' }) {
  const [markets, setMarkets] = useState([])
  const [selectedMarket, setSelectedMarket] = useState('KRW-BTC')
  const [strategies, setStrategies] = useState([])
  const [totalAllocation, setTotalAllocation] = useState(0)
  const [loadingId, setLoadingId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [toast, setToast] = useState('')
  const toastTimer = useRef(null)
  const [ratioDrafts, setRatioDrafts] = useState({})
  const [timeframeDrafts, setTimeframeDrafts] = useState({})
  const [stopLossDrafts, setStopLossDrafts] = useState({})
  const [takeProfitDrafts, setTakeProfitDrafts] = useState({})
  const [catalogOpen, setCatalogOpen] = useState(false)
  const marketAllocatedPercent = strategies
    .filter((strategy) => strategy.selected)
    .reduce((total, strategy) => total + strategy.invest_ratio * 100, 0)
  const allocatedPercent = totalAllocation * 100
  const visibleStrategies = strategies.filter((strategy) => strategy.selected || strategy.has_open_position)
  const availableStrategies = strategies.filter((strategy) => !strategy.selected && !strategy.has_open_position)

  useEffect(() => () => clearTimeout(toastTimer.current), [])

  const showToast = (message) => {
    setToast(message)
    clearTimeout(toastTimer.current)
    toastTimer.current = setTimeout(() => setToast(''), 3_500)
  }

  /** 서버 값은 갱신하되 사용자가 편집 중인 입력값은 5초 폴링으로 덮지 않습니다. */
  const loadStrategies = () => {
    setError('')
    Promise.all([
      apiFetch(`/strategies?mode=${executionMode}&market=${selectedMarket}`),
      apiFetch('/strategies/markets'),
      apiFetch(`/strategies/allocation?mode=${executionMode}`),
    ])
      .then(([items, marketItems, allocation]) => {
        setStrategies(items)
        setMarkets(marketItems)
        setTotalAllocation(allocation.total_ratio)
        setRatioDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? Math.round(item.invest_ratio * 100)]),
        ))
        setTimeframeDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? item.selected_timeframe_minutes]),
        ))
        setStopLossDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.stop_loss_rate ? item.stop_loss_rate * 100 : '')]),
        ))
        setTakeProfitDrafts((current) => Object.fromEntries(
          items.map((item) => [item.id, current[item.id] ?? (item.take_profit_rate ? item.take_profit_rate * 100 : '')]),
        ))
      })
      .catch((requestError) => setError(requestError.message))
  }

  usePolling(loadStrategies, REFRESH_INTERVAL_MS, `${selectedMarket}:${executionMode}`)

  const replaceStrategy = (updated) => {
    setStrategies((current) => current.map((item) => (item.id === updated.id ? updated : item)))
  }

  const toggleStrategy = async (strategy) => {
    const draftPercent = Number(ratioDrafts[strategy.id])
    const draftTimeframe = Number(timeframeDrafts[strategy.id])
    let forceDisable = false
    if (strategy.selected && strategy.has_open_position) {
      forceDisable = window.confirm(
        '이 전략으로 보유 중인 포지션이 있습니다.\n\n전략을 해제하면 이후 자동 매도 신호와 손절·익절 감시가 중단되며, 보유 자산은 그대로 남습니다.\n\n그래도 전략을 해제하시겠습니까?',
      )
      if (!forceDisable) return
    }
    if (!strategy.selected && (!Number.isFinite(draftPercent) || draftPercent < 1 || draftPercent > 100)) {
      showToast('투자 비율은 1%부터 100% 사이로 입력해 주세요.')
      return
    }

    const expectedTotal = allocatedPercent + draftPercent
    if (!strategy.selected && expectedTotal > 100) {
      showToast(`전략을 선택하면 투자 비율 합계가 ${Math.round(expectedTotal)}%가 됩니다. 합계는 100%를 넘을 수 없습니다.`)
      return
    }

    setLoadingId(strategy.id)
    setError('')
    try {
      replaceStrategy(await apiFetch(`/strategies/${strategy.id}/subscription?mode=${executionMode}&market=${strategy.market}`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: !strategy.selected,
          force_disable: forceDisable,
          invest_ratio: strategy.selected ? strategy.invest_ratio : draftPercent / 100,
          timeframe_minutes: strategy.selected ? strategy.selected_timeframe_minutes : draftTimeframe,
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
    const percent = Number(ratioDrafts[strategy.id])
    if (!Number.isFinite(percent) || percent < 1 || percent > 100) {
      showToast('투자 비율은 1%부터 100% 사이로 입력해 주세요.')
      return
    }

    const expectedTotal = allocatedPercent - strategy.invest_ratio * 100 + percent
    if (expectedTotal > 100) {
      showToast(`저장하면 투자 비율 합계가 ${Math.round(expectedTotal)}%가 됩니다. 다른 전략의 비율을 먼저 낮춰 주세요.`)
      return
    }
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
      const timeframe = Number(timeframeDrafts[strategy.id])
      const updated = await apiFetch(`/strategies/${strategy.id}/subscription?mode=${executionMode}&market=${strategy.market}`, {
        method: 'PUT',
        body: JSON.stringify({
          enabled: true,
          invest_ratio: percent / 100,
          timeframe_minutes: timeframe,
          stop_loss_rate: stopLoss / 100,
          take_profit_rate: takeProfit / 100,
        }),
      })
      replaceStrategy(updated)
      loadStrategies()
      setNotice(`${strategy.name} 설정을 ${timeframe}분봉, 투자 비율 ${percent}%로 저장했습니다.`)
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
        ? `${strategy.market}를 설정한 투자 비율 한도 내에서 실제 시장가 매수합니다. 계속하시겠습니까?`
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

  const strategyCard = (strategy) => (
    <StrategyCard
      key={strategy.id}
      strategy={strategy}
      executionMode={executionMode}
      loading={loadingId === strategy.id}
      ratioDraft={ratioDrafts[strategy.id] ?? ''}
      timeframeDraft={timeframeDrafts[strategy.id] ?? strategy.selected_timeframe_minutes}
      stopLossDraft={stopLossDrafts[strategy.id] ?? ''}
      takeProfitDraft={takeProfitDrafts[strategy.id] ?? ''}
      onRatioChange={(id, value) => setRatioDrafts((current) => ({ ...current, [id]: value }))}
      onTimeframeChange={(id, value) => setTimeframeDrafts((current) => ({ ...current, [id]: value }))}
      onStopLossChange={(id, value) => setStopLossDrafts((current) => ({ ...current, [id]: value }))}
      onTakeProfitChange={(id, value) => setTakeProfitDrafts((current) => ({ ...current, [id]: value }))}
      onToggle={toggleStrategy}
      onSave={saveSettings}
      onTestSignal={sendTestSignal}
      onManualSell={manualSell}
    />
  )

  return (
    <article className={panelStyles.panel}>
      <header>
        <div><h3>자동매매 전략</h3><p>현재 사용하는 전략을 우선 표시합니다. 계산값은 5초마다 자동 갱신됩니다.</p></div>
        <span className={styles.allocationBadge}>투자 비율 {Math.round(allocatedPercent)}%</span>
      </header>

      <div className={styles.content}>
        <div className={styles.marketSelector}>
          <div><strong>거래 종목</strong><small>종목을 선택한 뒤 전략을 설정하세요.</small></div>
          <select value={selectedMarket} onChange={(event) => {
            setSelectedMarket(event.target.value)
            setCatalogOpen(false)
            setRatioDrafts({})
            setTimeframeDrafts({})
            setStopLossDrafts({})
            setTakeProfitDrafts({})
          }}>
            {markets.map((market) => (
              <option key={market.code} value={market.code}>
                {market.display_name} ({market.code})
              </option>
            ))}
          </select>
        </div>
        <div className={styles.groupTitle}>
          <div><strong>사용 중인 전략</strong><span>{visibleStrategies.length}개</span></div>
          <small>포지션이 남은 해제 전략도 이 영역에 표시됩니다.</small>
        </div>
        {visibleStrategies.map(strategyCard)}
        {!error && strategies.length > 0 && visibleStrategies.length === 0 && (
          <div className={styles.noSelection}><Layers3 size={24} /><strong>선택한 전략이 없습니다.</strong><span>다른 전략 보기에서 자동매매 전략을 선택하세요.</span></div>
        )}

        {availableStrategies.length > 0 && (
          <div className={styles.catalog}>
            <button className={styles.catalogToggle} onClick={() => setCatalogOpen((current) => !current)} aria-expanded={catalogOpen}>
              <span><Layers3 size={17} /> 다른 전략 보기 <b>{availableStrategies.length}</b></span>
              <ChevronDown className={catalogOpen ? styles.chevronOpen : ''} size={18} />
            </button>
            {catalogOpen && <div className={styles.catalogList}>{availableStrategies.map(strategyCard)}</div>}
          </div>
        )}

        {!error && strategies.length === 0 && <div className={panelStyles.empty}>제공 중인 전략이 없습니다.</div>}
        {error && <p className={styles.error}>{error}</p>}
        {notice && <p className={styles.success}>{notice}</p>}
        <p className={styles.notice}>투자 비율은 모든 종목과 전략의 합계가 100%를 넘을 수 없습니다. 현재 종목 배정 합계는 {Math.round(marketAllocatedPercent)}%입니다.</p>
      </div>
      {toast && <div className={styles.toast} role="alert">{toast}</div>}
    </article>
  )
}
