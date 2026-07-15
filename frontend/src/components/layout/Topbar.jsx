import { Bell, Menu, Search } from 'lucide-react'
import styles from './Topbar.module.css'

export default function Topbar({ onMenu }) {
  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <button className={styles.menu} onClick={onMenu} aria-label="사이드바 열기"><Menu size={20} /></button>
        <div>
          <h1>트레이딩 대시보드</h1>
          <p>안녕하세요, 김도현님. 오늘의 자동매매 현황입니다.</p>
        </div>
      </div>

      <div className={styles.actions}>
        <div className={styles.connection}>
          <i />
          <span><strong>LIVE</strong><small>Upbit 연결됨</small></span>
        </div>
        <button className={styles.iconButton}><Search size={18} /></button>
        <button className={`${styles.iconButton} ${styles.alert}`}><Bell size={18} /><b>3</b></button>
        <div className={styles.profile}>
          <div>DK</div>
          <span><strong>김도현</strong><small>Admin</small></span>
        </div>
      </div>
    </header>
  )
}
