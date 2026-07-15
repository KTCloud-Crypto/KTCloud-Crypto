import { useState } from 'react'
import styles from './QuickOrder.module.css'

export default function QuickOrder() {
  const [side, setSide] = useState('buy')
  const [ratio, setRatio] = useState('50%')

  return (
    <aside className={styles.panel}>
      <header><div><h3>빠른 주문</h3><p>수동 주문 실행</p></div></header>
      <div className={styles.tabs}>
        <button className={side === 'buy' ? styles.activeBuy : ''} onClick={() => setSide('buy')}>매수</button>
        <button className={side === 'sell' ? styles.activeSell : ''} onClick={() => setSide('sell')}>매도</button>
      </div>

      <label><span>거래 종목</span><button className={styles.select}><i>₿</i><strong>KRW-BTC</strong><small>Bitcoin</small><b>⌄</b></button></label>
      <label><span>주문 유형</span><button className={styles.select}><strong>시장가 주문</strong><b>⌄</b></button></label>
      <label><span>주문 금액</span><div className={styles.money}><input defaultValue="100,000" /><span>KRW</span></div></label>

      <div className={styles.ratios}>
        {['10%','25%','50%','100%'].map((item) => <button key={item} className={ratio === item ? styles.selected : ''} onClick={() => setRatio(item)}>{item}</button>)}
      </div>

      <div className={styles.estimate}>
        <div><span>주문 가능</span><strong>₩3,841,220</strong></div>
        <div><span>예상 수량</span><strong>0.000656 BTC</strong></div>
        <div><span>예상 수수료</span><strong>₩50</strong></div>
      </div>

      <button className={side === 'buy' ? styles.buyButton : styles.sellButton}>
        BTC {side === 'buy' ? '매수' : '매도'} 주문
      </button>
      <p>주문 전 리스크 한도를 자동으로 확인합니다.</p>
    </aside>
  )
}
