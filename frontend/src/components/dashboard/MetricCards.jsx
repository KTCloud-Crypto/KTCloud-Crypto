import { Clock3, ShieldCheck, TrendingUp, WalletCards } from 'lucide-react'
import styles from './MetricCards.module.css'

const items = [
  { icon: WalletCards, tone: 'blue', badge: '+2.84%', label: '총 평가 자산', value: '₩24,892,450', note: '전일 대비 +₩686,320' },
  { icon: TrendingUp, tone: 'green', badge: '+₩184,320', label: '오늘 실현 손익', value: '+₩184,320', note: '총 18건 거래 · 승률 72.2%' },
  { icon: Clock3, tone: 'purple', badge: '4개 실행 중', label: '활성 전략', value: '4 / 6', note: '최근 신호 38초 전' },
  { icon: ShieldCheck, tone: 'orange', badge: '안전', label: '일일 손실 한도', value: '12.8%', note: '₩128,400 / ₩1,000,000', progress: 12.8 },
]

export default function MetricCards() {
  return (
    <div className={styles.grid}>
      {items.map(({ icon: Icon, tone, badge, label, value, note, progress }) => (
        <article className={styles.card} key={label}>
          <div className={styles.top}>
            <span className={`${styles.icon} ${styles[tone]}`}><Icon size={20} /></span>
            <span className={styles.badge}>{badge}</span>
          </div>
          <span className={styles.label}>{label}</span>
          <strong className={value.startsWith('+') ? styles.positive : ''}>{value}</strong>
          {progress !== undefined && <div className={styles.progress}><span style={{ width: `${progress}%` }} /></div>}
          <small>{note}</small>
        </article>
      ))}
    </div>
  )
}
