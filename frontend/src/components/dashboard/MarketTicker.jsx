import { useState } from 'react'
import { apiFetch } from '../../api/client'
import { usePolling } from '../../hooks/usePolling'
import { coinIconForCurrency } from '../../utils/coinIcons'
import styles from './MarketTicker.module.css'

const REFRESH_INTERVAL_MS = 5_000

const formatWon = (value) => Math.round(value ?? 0).toLocaleString('ko-KR')

const formatTradeValue = (value) => {
  const hundredMillion = (value ?? 0) / 100_000_000
  if (hundredMillion >= 10_000) return `${(hundredMillion / 10_000).toLocaleString('ko-KR', { maximumFractionDigits: 1 })}조원`
  return `${hundredMillion.toLocaleString('ko-KR', { maximumFractionDigits: 0 })}억원`
}

const symbolFromMarket = (market) => market.split('-').at(-1)
function Change({ item, detailed = false }) {
  const isUp = item.change_rate > 0
  const isDown = item.change_rate < 0
  const changeClass = isUp ? styles.up : isDown ? styles.down : styles.flat
  const sign = isUp ? '+' : isDown ? '-' : ''

  if (!detailed) {
    return (
      <span className={changeClass}>
        {isUp ? '▲' : isDown ? '▼' : '－'} {Math.abs(item.change_rate).toFixed(2)}%
      </span>
    )
  }

  return (
    <span className={`${styles.boardChange} ${changeClass}`}>
      <strong>{sign}{Math.abs(item.change_rate).toFixed(2)}%</strong>
      <small>{sign}{formatWon(Math.abs(item.change_price))}원</small>
    </span>
  )
}

/** 홈에서는 시세 보드, 투자 화면에서는 좁은 실시간 시세 바로 표시합니다. */
export default function MarketTicker({ variant = 'compact' }) {
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')

  const load = () => apiFetch('/strategies/markets/tickers')
    .then((items) => {
      setTickers(items)
      setError('')
    })
    .catch((requestError) => setError(requestError.message))

  usePolling(load, REFRESH_INTERVAL_MS)

  if (variant === 'board') {
    return (
      <section className={styles.board} aria-labelledby="market-board-title">
        <header className={styles.boardHeader}>
          <div>
            <span className={styles.liveDot} aria-hidden="true" />
            <div>
              <h2 id="market-board-title">실시간 가상자산 시세</h2>
              <p>SignalTrade 지원 종목 · 5초마다 갱신</p>
            </div>
          </div>
          <span className={styles.marketCount}>KRW 마켓 {tickers.length || 6}종</span>
        </header>

        <div className={styles.boardTable} role="table" aria-label="지원 종목 실시간 시세">
          <div className={styles.boardTableHeader} role="row">
            <span role="columnheader">자산명</span>
            <span role="columnheader">현재가</span>
            <span role="columnheader">전일 대비</span>
            <span role="columnheader">24시간 거래대금</span>
          </div>

          {error ? (
            <p className={styles.boardMessage}>시세 정보를 잠시 불러오지 못했습니다. 자동으로 다시 시도합니다.</p>
          ) : tickers.length === 0 ? (
            <p className={styles.boardMessage}>최신 시세를 불러오는 중입니다.</p>
          ) : tickers.map((item) => {
            const symbol = symbolFromMarket(item.market)
            const icon = coinIconForCurrency(symbol)
            return (
              <div className={styles.boardRow} role="row" key={item.market}>
                <span className={styles.asset} role="cell">
                  <span className={styles.assetSymbol}>
                    <span>{symbol.slice(0, 2)}</span>
                    <img src={icon} alt="" onError={(event) => event.currentTarget.remove()} />
                  </span>
                  <span><strong>{item.display_name}</strong><small>{symbol}</small></span>
                </span>
                <strong className={styles.boardPrice} role="cell">{formatWon(item.price)}원</strong>
                <Change item={item} detailed />
                <span className={styles.tradeValue} role="cell">{formatTradeValue(item.trade_value_24h)}</span>
              </div>
            )
          })}
        </div>
      </section>
    )
  }

  if (error || tickers.length === 0) return null

  return (
    <div className={styles.ticker} role="list" aria-label="실시간 시세">
      {tickers.map((item) => {
        const symbol = symbolFromMarket(item.market)
        const icon = coinIconForCurrency(symbol)
        return (
          <div className={styles.item} role="listitem" key={item.market}>
            <span className={styles.compactAsset}>
              <span className={styles.compactIcon}>
                <span>{symbol.slice(0, 2)}</span>
                <img src={icon} alt="" onError={(event) => event.currentTarget.remove()} />
              </span>
              <span className={styles.compactIdentity}>
                <strong>{item.display_name}</strong>
                <small>{symbol}/KRW</small>
              </span>
            </span>
            <span className={styles.compactQuote}>
              <span className={styles.price}>{Math.round(item.price).toLocaleString()}원</span>
              <Change item={item} />
            </span>
          </div>
        )
      })}
    </div>
  )
}
