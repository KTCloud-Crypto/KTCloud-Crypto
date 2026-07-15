import styles from './RiskPanel.module.css'

export default function RiskPanel() {
  return (
    <article className={styles.panel}>
      <header><div><h3>리스크 상태</h3><p>계정 안전 지표</p></div><span>● 정상</span></header>
      <div className={styles.gauge}>
        <svg viewBox="0 0 180 105">
          <path className={styles.bg} d="M20 90a70 70 0 0 1 140 0" />
          <path className={styles.value} d="M20 90a70 70 0 0 1 140 0" />
        </svg>
        <div><strong>24</strong><span>/ 100</span><small>낮은 위험</small></div>
      </div>
      <div className={styles.list}>
        {[['일일 손실 한도','12.8%',12.8],['최대 포지션 비율','41.2%',41.2],['API 호출 사용량','18.6%',18.6]].map(([label,value,width]) => (
          <div key={label}>
            <span>{label}</span><strong>{value}</strong>
            <div><i style={{ width: `${width}%` }} /></div>
            <small>{label === '일일 손실 한도' ? '₩128,400 / ₩1,000,000' : label === '최대 포지션 비율' ? '설정 한도 70%' : '분당 112 / 600회'}</small>
          </div>
        ))}
      </div>
      <button>리스크 설정 관리</button>
    </article>
  )
}
