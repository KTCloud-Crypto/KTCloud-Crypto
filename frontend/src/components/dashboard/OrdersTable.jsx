import styles from './OrdersTable.module.css'

const rows = [
  ['10:42:18','BTC','매수','MA 돌파','₩100,000','₩152,420,000','₩50','체결 완료'],
  ['10:31:04','ETH','매도','RSI 반전','₩253,400','₩5,836,000','₩127','체결 완료'],
  ['10:18:51','SOL','매수','수동 주문','₩150,000','₩248,600','₩75','처리 중'],
  ['09:58:32','XRP','매도','볼린저밴드','₩82,900','₩3,209','₩41','취소됨'],
]

export default function OrdersTable() {
  return (
    <article className={styles.panel}>
      <header><div><h3>최근 주문 내역</h3><p>최근 자동·수동 주문 실행 기록</p></div><button>전체 보기</button></header>
      <div className={styles.scroll}>
        <table>
          <thead><tr><th>주문 시간</th><th>종목</th><th>구분</th><th>전략</th><th>주문 금액</th><th>체결 가격</th><th>수수료</th><th>상태</th></tr></thead>
          <tbody>
            {rows.map(([time,symbol,side,strategy,amount,price,fee,status]) => (
              <tr key={`${time}-${symbol}`}>
                <td><strong>{time}</strong><span>2026.07.13</span></td>
                <td><div className={styles.asset}><i className={styles[symbol.toLowerCase()]}>{symbol === 'BTC' ? '₿' : symbol[0]}</i><span><strong>{symbol}</strong><small>KRW-{symbol}</small></span></div></td>
                <td><span className={side === '매수' ? styles.buy : styles.sell}>{side}</span></td>
                <td><strong>{strategy}</strong><span>{strategy === '수동 주문' ? '수동' : '자동'}</span></td>
                <td><strong>{amount}</strong></td>
                <td><strong>{price}</strong></td>
                <td>{fee}</td>
                <td><span className={status === '체결 완료' ? styles.filled : status === '처리 중' ? styles.pending : styles.cancelled}>{status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  )
}
