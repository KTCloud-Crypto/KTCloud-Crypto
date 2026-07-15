import styles from './MarketStrip.module.css'

const markets = [
  ['₿', 'BTC', 'Bitcoin', '₩152,430,000', '+2.41%', 'up'],
  ['◆', 'ETH', 'Ethereum', '₩5,842,000', '+1.18%', 'up'],
  ['X', 'XRP', 'Ripple', '₩3,216', '-0.73%', 'down'],
  ['S', 'SOL', 'Solana', '₩248,900', '+4.07%', 'up'],
]

export default function MarketStrip() {
  return (
    <section className={styles.wrapper}>
      <div className={styles.track}>
        {markets.map(([mark, code, name, price, change, trend]) => (
          <article key={code} className={styles.card}>
            <div className={`${styles.coin} ${styles[code.toLowerCase()]}`}>{mark}</div>
            <div className={styles.info}>
              <div><strong>{code}</strong><span>{name}</span></div>
              <b>{price}</b>
            </div>
            <span className={trend === 'up' ? styles.up : styles.down}>{change}</span>
            <svg viewBox="0 0 120 38" preserveAspectRatio="none">
              <path className={trend === 'up' ? styles.areaUp : styles.areaDown} d={trend === 'up' ? 'M0 32 12 26 23 29 35 20 48 23 60 14 74 18 86 10 100 13 120 4 120 38 0 38Z' : 'M0 12 14 8 28 14 42 11 58 19 73 16 88 27 102 23 120 32 120 38 0 38Z'} />
              <path className={trend === 'up' ? styles.lineUp : styles.lineDown} d={trend === 'up' ? 'M0 32 12 26 23 29 35 20 48 23 60 14 74 18 86 10 100 13 120 4' : 'M0 12 14 8 28 14 42 11 58 19 73 16 88 27 102 23 120 32'} />
            </svg>
          </article>
        ))}
      </div>
    </section>
  )
}
