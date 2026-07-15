import { useState } from 'react'
import styles from './PerformancePanel.module.css'

export default function PerformancePanel() {
  const [period, setPeriod] = useState('1W')
  return (
    <article className={styles.panel}>
      <header>
        <div><h3>자산 수익률 <span>+8.42%</span></h3><p>자동매매 계정 누적 자산 변화</p></div>
        <div className={styles.periods}>
          {['1D','1W','1M','3M','1Y'].map((item) => (
            <button key={item} className={period === item ? styles.active : ''} onClick={() => setPeriod(item)}>{item}</button>
          ))}
        </div>
      </header>
      <div className={styles.summary}>
        <div><span>현재 평가금액</span><strong>₩24,892,450</strong></div>
        <div><span><i className={styles.blue} />포트폴리오</span><span><i className={styles.gray} />BTC 기준</span></div>
      </div>
      <div className={styles.chart}>
        <svg viewBox="0 0 900 330" preserveAspectRatio="none">
          <defs>
            <linearGradient id="portfolioFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6c8cff" stopOpacity=".32" />
              <stop offset="100%" stopColor="#6c8cff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <g className={styles.grid}>
            <path d="M0 30H900M0 95H900M0 160H900M0 225H900M0 290H900" />
            <path d="M100 0V310M260 0V310M420 0V310M580 0V310M740 0V310" />
          </g>
          <path className={styles.benchmark} d="M0 255 C70 245 100 230 160 235 S250 212 310 216 S405 200 470 194 S560 179 630 184 S735 163 800 168 S865 157 900 146" />
          <path fill="url(#portfolioFill)" d="M0 270 C55 260 92 247 135 251 S220 217 270 223 S330 187 385 196 S460 135 520 151 S610 100 675 117 S760 67 815 82 S870 44 900 51 L900 330 L0 330 Z" />
          <path className={styles.line} d="M0 270 C55 260 92 247 135 251 S220 217 270 223 S330 187 385 196 S460 135 520 151 S610 100 675 117 S760 67 815 82 S870 44 900 51" />
          <circle className={styles.point} cx="900" cy="51" r="6" />
        </svg>
        <div className={styles.xlabels}><span>7/07</span><span>7/08</span><span>7/09</span><span>7/10</span><span>7/11</span><span>7/12</span><span>7/13</span></div>
      </div>
    </article>
  )
}
