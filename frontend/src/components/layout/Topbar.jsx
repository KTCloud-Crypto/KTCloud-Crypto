import { Menu, Webhook } from 'lucide-react'
import styles from './Topbar.module.css'

export default function Topbar({ onMenu, user }) {
  return (
    <header className={styles.topbar}>
      <div className={styles.left}>
        <button className={styles.menu} onClick={onMenu} aria-label="사이드바 열기"><Menu size={20} /></button>
        <div>
          <h1>트레이딩 대시보드</h1>
          <p>안녕하세요, {user?.nickname || ''}님. 자동매매 현황입니다.</p>
        </div>
      </div>

      <div className={styles.actions}>
        <div className={styles.connection}>
          <Webhook size={14} />
          <span><strong>{user?.bot_enabled ? '수신 중' : '중지됨'}</strong><small>웹훅 신호</small></span>
        </div>
        <div className={styles.profile}>
          <div>{user?.nickname?.slice(0, 2) || '-'}</div>
          <span><strong>{user?.nickname || '-'}</strong><small>@{user?.username || '-'}</small></span>
        </div>
      </div>
    </header>
  )
}
