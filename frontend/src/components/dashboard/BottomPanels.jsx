import { useEffect, useState } from 'react'
import styles from './BottomPanels.module.css'

export default function BottomPanels() {
  const [time, setTime] = useState('')

  useEffect(() => {
    const update = () => setTime(new Intl.DateTimeFormat('ko-KR', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).format(new Date()))
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className={styles.grid}>
      <Panel title="보유 자산" subtitle="현재 계정 포트폴리오">
        {[
          ['₿','Bitcoin','BTC · 0.0831','₩12,668,933','+6.42%','btc'],
          ['◆','Ethereum','ETH · 1.284','₩7,501,128','+3.18%','eth'],
          ['S','Solana','SOL · 3.42','₩851,238','-1.06%','sol'],
          ['₩','원화','KRW','₩3,871,151','15.55%','krw'],
        ].map(([mark,name,sub,value,change,tone]) => (
          <div className={styles.assetRow} key={name}>
            <div className={styles.asset}><i className={styles[tone]}>{mark}</i><span><strong>{name}</strong><small>{sub}</small></span></div>
            <div className={styles.value}><strong>{value}</strong><span className={change.startsWith('-') ? styles.down : change.startsWith('+') ? styles.up : ''}>{change}</span></div>
          </div>
        ))}
      </Panel>

      <Panel title="Webhook 이벤트" subtitle="최근 TradingView 신호 수신">
        {[
          ['BTC BUY 신호 수신','ma-cross-v1 · 38초 전','200 OK','buyEvent'],
          ['ETH SELL 신호 수신','rsi-reversal-v2 · 12분 전','200 OK','sellEvent'],
          ['중복 신호 차단','signal_id 중복 · 28분 전','409','warnEvent'],
        ].map(([title,sub,status,tone]) => (
          <div className={styles.event} key={title}>
            <i className={styles[tone]} />
            <span><strong>{title}</strong><small>{sub}</small></span>
            <b>{status}</b>
          </div>
        ))}
      </Panel>

      <Panel title="시스템 상태" subtitle="서비스별 연결 상태" right={time}>
        {[
          ['FastAPI Server','정상'],
          ['PostgreSQL','정상'],
          ['Upbit REST API','42ms'],
          ['WebSocket','연결됨'],
          ['Redis Queue','0 대기'],
        ].map(([name,status]) => (
          <div className={styles.service} key={name}><span><i />{name}</span><strong>{status}</strong></div>
        ))}
      </Panel>
    </div>
  )
}

function Panel({ title, subtitle, right, children }) {
  return (
    <article className={styles.panel}>
      <header><div><h3>{title}</h3><p>{subtitle}</p></div>{right && <span>{right}</span>}</header>
      <div className={styles.content}>{children}</div>
    </article>
  )
}
