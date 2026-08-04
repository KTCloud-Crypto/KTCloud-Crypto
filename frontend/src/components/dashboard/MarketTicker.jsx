import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import styles from './MarketTicker.module.css'

const REFRESH_INTERVAL_MS = 5_000

/** 홈, 모의투자, 실전투자 화면에서 공통으로 쓰는 실시간 시세 바입니다. */
export default function MarketTicker() {
  const [tickers, setTickers] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    const load = () => {
      apiFetch('/strategies/markets/tickers')
        .then((items) => {
          if (active) {
            setTickers(items)
            setError('')
          }
        })
        .catch((requestError) => {
          if (active) setError(requestError.message)
        })
    }
    load()
    const timer = window.setInterval(load, REFRESH_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  if (error) return null
  if (tickers.length === 0) return null

  return (
    <div className={styles.ticker} role="list" aria-label="실시간 시세">
      {tickers.map((item) => {
        const isUp = item.change_rate > 0
        const isDown = item.change_rate < 0
        const changeClass = isUp ? styles.up : isDown ? styles.down : styles.flat
        return (
          <div className={styles.item} role="listitem" key={item.market}>
            <span className={styles.name}>{item.display_name}</span>
            <span className={styles.price}>{Math.round(item.price).toLocaleString()}원</span>
            <span className={changeClass}>
              {isUp ? '▲' : isDown ? '▼' : '－'} {Math.abs(item.change_rate).toFixed(2)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
