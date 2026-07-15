import {
  Activity, BarChart3, BookOpen, Boxes, CircleUserRound, Gauge,
  KeyRound, LayoutDashboard, ListOrdered, Menu, Settings, ShieldCheck,
  SlidersHorizontal, Webhook, X
} from 'lucide-react'
import styles from './Sidebar.module.css'

const items = [
  ['OVERVIEW', [
    [LayoutDashboard, '대시보드'],
    [BarChart3, '시장 현황'],
    [ListOrdered, '주문 내역', '12'],
    [Boxes, '보유 자산'],
  ]],
  ['AUTOMATION', [
    [SlidersHorizontal, '전략 관리'],
    [Webhook, '웹훅 관리', 'dot'],
    [ShieldCheck, '리스크 관리'],
    [BookOpen, '시스템 로그'],
  ]],
  ['SYSTEM', [
    [KeyRound, 'API 키 관리'],
    [Settings, '환경 설정'],
  ]],
]

export default function Sidebar({ open, onClose, active, onSelect }) {
  return (
    <>
      <aside className={`${styles.sidebar} ${open ? styles.open : ''}`}>
        <div className={styles.top}>
          <div className={styles.brand}>
            <span><Activity size={22} /></span>
            <b>AutoTrade</b>
          </div>
          <button className={styles.close} onClick={onClose} aria-label="사이드바 닫기"><X size={20} /></button>
        </div>

        <div className={styles.workspace}>
          <div>AT</div>
          <span><strong>AutoTrade Team</strong><small>Production</small></span>
          <Menu size={16} />
        </div>

        <nav className={styles.nav}>
          {items.map(([label, links]) => (
            <section key={label}>
              <h4>{label}</h4>
              {links.map(([Icon, name, badge]) => (
                <button
                  key={name}
                  className={active === name ? styles.active : ''}
                  onClick={() => { onSelect(name); onClose() }}
                >
                  <Icon size={18} />
                  <span>{name}</span>
                  {badge === 'dot' ? <i className={styles.dot} /> : badge ? <b>{badge}</b> : null}
                </button>
              ))}
            </section>
          ))}
        </nav>

        <div className={styles.footer}>
          <div className={styles.health}>
            <div><span><i /> 시스템 정상</span><small>99.99%</small></div>
            <div className={styles.healthBar}><span /></div>
            <p>모든 서비스가 정상 작동 중입니다.</p>
          </div>
          <div className={styles.profile}>
            <div className={styles.avatar}>DK</div>
            <span><strong>김도현</strong><small>관리자</small></span>
            <CircleUserRound size={18} />
          </div>
        </div>
      </aside>
      {open && <button className={styles.overlay} onClick={onClose} aria-label="사이드바 닫기" />}
    </>
  )
}
