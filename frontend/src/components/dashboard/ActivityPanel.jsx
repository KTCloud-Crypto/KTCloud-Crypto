import PagedList from './PagedList'
import { useState } from 'react'
import { Activity, BellRing, BriefcaseBusiness, ReceiptText } from 'lucide-react'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import { formatNumber, formatUtcDateTime } from '../../utils/format'
import { metricEntries } from '../../utils/strategyDisplay'
import panelStyles from './Panel.module.css'
import styles from './ActivityPanel.module.css'

const STATUS_LABELS = {
  simulated: '모의 완료',
  simulated_pending: '모의 처리 중',
  simulated_success: '모의 체결',
  simulated_failed: '모의 실패',
  simulated_skipped: '건너뜀',
  success: '체결 성공',
  submitted: '주문 접수',
  partially_filled: '부분 체결',
  validation_failed: '검사 실패',
  failed: '주문 실패',
  cancelled: '주문 취소',
  ready: '주문 준비',
  skipped: '건너뜀',
  uncertain: '확인 필요',
  reconciled: '동기화 완료',
}

const SOURCE_LABELS = {
  engine: '자동 계산',
  test: '테스트',
  stop_loss: '손절',
  take_profit: '목표 수익률',
  manual: '수동 매도',
  external_sync: '잔고 동기화',
}

function statusClass(status) {
  if (['success', 'simulated', 'simulated_success', 'reconciled'].includes(status)) return panelStyles.success
  if (['submitted', 'partially_filled', 'ready', 'uncertain'].includes(status) || status.includes('skipped')) return panelStyles.neutral
  return panelStyles.failed
}

export default function ActivityPanel({ mode }) {
  const [activeTab, setActiveTab] = useState('positions')
  const [positions, setPositions] = useState([])
  const [signals, setSignals] = useState([])
  const [executions, setExecutions] = useState([])
  const [trades, setTrades] = useState([])
  const [error, setError] = useState('')

  const load = () => {
    const requests = [
      apiFetch(`/strategies/positions?mode=${mode}&all_markets=true`),
      apiFetch(`/strategies/signals?mode=${mode}`),
      apiFetch(`/strategies/executions?mode=${mode}`),
      ...(mode === 'live' ? [apiFetch('/trades')] : []),
    ]
    Promise.all(requests)
      .then(([positionItems, signalItems, executionItems, tradeItems = []]) => {
        setPositions(positionItems)
        setSignals(signalItems)
        setExecutions(executionItems)
        setTrades(tradeItems)
        setError('')
      })
      .catch((requestError) => setError(requestError.message))
  }

  usePolling(load, 5_000)

  const tabs = [
    { id: 'positions', label: '포지션', count: positions.length, icon: BriefcaseBusiness },
    { id: 'signals', label: '전략 신호', count: signals.length, icon: BellRing },
    { id: 'executions', label: '실행 결과', count: executions.length, icon: Activity },
    ...(mode === 'live' ? [{ id: 'trades', label: '거래 내역', count: trades.length, icon: ReceiptText }] : []),
  ]

  return (
    <article className={`${panelStyles.panel} ${styles.panel}`}>
      <header>
        <div>
          <h3>자동매매 활동</h3>
          <p>포지션과 신호, 사용자별 주문 처리 결과를 탭으로 확인합니다. 5초마다 자동 갱신됩니다.</p>
        </div>
      </header>

      <div className={styles.tabs} role="tablist" aria-label="자동매매 활동">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              className={activeTab === tab.id ? styles.activeTab : ''}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              aria-selected={activeTab === tab.id}
            >
              <Icon size={16} />
              {tab.label}
              <span>{tab.count}</span>
            </button>
          )
        })}
      </div>

      {error && <div className={panelStyles.empty}>{error}</div>}

      {!error && activeTab === 'positions' && (
        <div className={panelStyles.scroll}>
          <table>
            <thead><tr><th>전략</th><th>설정</th><th>{mode === 'simulated' ? '모의 포지션' : '실전 포지션'}</th></tr></thead>
            <tbody>
              {positions.map((position) => {
                const holding = mode === 'simulated' ? position.paper_status === 'holding' : position.status === 'holding'
                const volume = mode === 'simulated' ? position.paper_volume : position.volume
                const average = mode === 'simulated' ? position.paper_average_buy_price : position.average_buy_price
                return (
                  <tr key={position.strategy_id}>
                    <td><strong>{position.strategy_name}</strong><span>{position.market}</span></td>
                    <td>{position.enabled ? `${position.timeframe_minutes}분 · ${Math.round(position.invest_ratio * 100)}%` : '선택 안 함'}</td>
                    <td><span className={holding ? panelStyles.success : panelStyles.neutral}>{holding ? `${volume.toFixed(8)} / ${formatNumber(average)}원` : '미보유'}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {positions.length === 0 && <div className={panelStyles.empty}>전략 포지션이 없습니다.</div>}
        </div>
      )}

      {!error && activeTab === 'signals' && (
        <div className={panelStyles.scroll}>
          <table>
            <thead><tr><th>전략</th><th>분봉</th><th>신호</th><th>종가</th><th>지표값</th><th>출처</th><th>발생 시각</th></tr></thead>
            <tbody>
              {signals.map((signal) => (
                <tr key={signal.id}>
                  <td><strong>{signal.strategy_name}</strong><span>{signal.market}</span></td>
                  <td>{signal.timeframe_minutes}분</td>
                  <td><span className={signal.action === 'buy' ? panelStyles.buy : panelStyles.sell}>{signal.action === 'buy' ? '매수' : '매도'}</span></td>
                  <td>{formatNumber(signal.close_price)}원</td>
                  <td>{metricEntries(signal.strategy_code, signal.metrics).map((metric) => `${metric.label} ${formatNumber(metric.value, 2)}`).join(' / ') || '-'}</td>
                  <td>{SOURCE_LABELS[signal.source] ?? signal.source}</td>
                  <td>{formatUtcDateTime(signal.candle_open_time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {signals.length === 0 && <div className={panelStyles.empty}>아직 확정된 전략 신호가 없습니다.</div>}
        </div>
      )}

      {!error && activeTab === 'executions' && (
        <div className={styles.executionList}>
          {executions.map((execution) => (
            <div key={execution.id} className={styles.executionCard}>
              <div className={styles.executionCardHeader}>
                <span className={`${execution.action === 'buy' ? panelStyles.buy : panelStyles.sell} ${styles.actionBadge}`}>
                  {execution.action === 'buy' ? '매수' : '매도'}
                </span>
                <span className={styles.executionStrategy}>
                  <strong>{execution.strategy_name}</strong>
                  <small>{execution.market}</small>
                </span>
                <span className={`${statusClass(execution.status)} ${styles.statusBadge}`}>
                  {STATUS_LABELS[execution.status] ?? execution.status}
                </span>
              </div>

              {(execution.error_message || execution.exit_reason) && (
                <p className={styles.executionReason}>
                  {execution.exit_reason ? `매도 사유: ${execution.exit_reason}` : execution.error_message}
                </p>
              )}

              <div className={styles.executionDetails}>
                {execution.entry_price != null && (
                  <span><small>매입 평균가</small><strong>{formatNumber(execution.entry_price)}원</strong></span>
                )}
                {execution.executed_volume ? (
                  <>
                    <span><small>체결가</small><strong>{formatNumber(execution.average_price ?? execution.price)}원</strong></span>
                    <span><small>수량</small><strong>{execution.executed_volume.toFixed(8)}</strong></span>
                  </>
                ) : null}
                {(execution.transaction_amount ?? execution.order_amount) != null && (
                  <span><small>체결금액</small><strong>{formatNumber(execution.transaction_amount ?? execution.order_amount)}원</strong></span>
                )}
              </div>

              <div className={styles.executionFooter}>
                <small>{formatUtcDateTime(execution.created_at)}</small>
                <span>
                  {execution.realized_profit_loss != null && (
                    <b className={execution.realized_profit_loss >= 0 ? styles.profitUp : styles.profitDown}>
                      {execution.realized_profit_loss >= 0 ? '+' : ''}{formatNumber(execution.realized_profit_loss)}원
                    </b>
                  )}
                  {execution.notification_sent && <small className={styles.notifiedTag}>알림 전송됨</small>}
                </span>
              </div>
            </div>
          ))}
          {executions.length === 0 && <div className={panelStyles.empty}>전략 실행 결과가 없습니다.</div>}
        </div>
      )}

      {!error && activeTab === 'trades' && (
        <PagedList
          items={trades}
          emptyLabel="거래 내역이 없습니다."
          renderItem={(trade) => (
            <div key={trade.id} className={styles.tradeCard}>
              <span className={trade.action === 'buy' ? panelStyles.buy : panelStyles.sell}>
                {trade.action === 'buy' ? '매수' : '매도'}
              </span>
              <div className={styles.tradeMain}>
                <strong>{trade.strategy_name || '이전 기록'} · {trade.ticker}</strong>
                <small>
                  {trade.price ? `${formatNumber(trade.price)}원` : '-'}
                  {trade.volume != null && ` · ${trade.volume}개`}
                </small>
              </div>
              <span className={statusClass(trade.status)}>{STATUS_LABELS[trade.status] ?? trade.status}</span>
              <span className={styles.tradeTime}>{formatUtcDateTime(trade.created_at)}</span>
            </div>
          )}
        />
      )}
    </article>
  )
}
