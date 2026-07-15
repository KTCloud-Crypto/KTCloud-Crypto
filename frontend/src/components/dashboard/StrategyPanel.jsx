import { Pause, Radio, TrendingUp } from 'lucide-react'
import styles from './StrategyPanel.module.css'

const strategies = [
  { name: 'BTC 이동평균 돌파', market: 'KRW-BTC · 15분봉', rate: '+12.48%', win: '68.2%', trades: '8회', recent: '38초 전', active: true, icon: TrendingUp, tone: 'blue' },
  { name: 'ETH RSI 반전', market: 'KRW-ETH · 1시간봉', rate: '+7.91%', win: '61.5%', trades: '4회', recent: '12분 전', active: true, icon: Radio, tone: 'purple' },
  { name: 'XRP 볼린저밴드', market: 'KRW-XRP · 5분봉', rate: '-1.24%', win: '48.7%', trades: '0회', recent: '일시 정지', active: false, icon: Pause, tone: 'gray' },
]

export default function StrategyPanel() {
  return (
    <article className={styles.panel}>
      <header><div><h3>자동매매 전략</h3><p>현재 실행 중인 전략 상태</p></div><button>+ 전략 추가</button></header>
      <div className={styles.list}>
        {strategies.map(({ name, market, rate, win, trades, recent, active, icon: Icon, tone }) => (
          <article key={name} className={!active ? styles.paused : ''}>
            <div className={`${styles.icon} ${styles[tone]}`}><Icon size={20} /></div>
            <div className={styles.main}>
              <div className={styles.title}>
                <div><strong>{name}</strong><span>{market}</span></div>
                <label className={styles.switch}><input type="checkbox" defaultChecked={active} /><span /></label>
              </div>
              <div className={styles.metrics}>
                <span><small>누적 수익률</small><b className={rate.startsWith('-') ? styles.down : styles.up}>{rate}</b></span>
                <span><small>승률</small><b>{win}</b></span>
                <span><small>오늘 거래</small><b>{trades}</b></span>
                <span><small>최근 신호</small><b>{recent}</b></span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </article>
  )
}
