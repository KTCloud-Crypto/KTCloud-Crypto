import { useState } from 'react'
import { Download, Octagon } from 'lucide-react'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import MarketStrip from '../components/dashboard/MarketStrip'
import MetricCards from '../components/dashboard/MetricCards'
import PerformancePanel from '../components/dashboard/PerformancePanel'
import QuickOrder from '../components/dashboard/QuickOrder'
import StrategyPanel from '../components/dashboard/StrategyPanel'
import RiskPanel from '../components/dashboard/RiskPanel'
import OrdersTable from '../components/dashboard/OrdersTable'
import BottomPanels from '../components/dashboard/BottomPanels'
import styles from './DashboardPage.module.css'

export default function DashboardPage() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeNav, setActiveNav] = useState('대시보드')

  return (
    <div className={styles.app}>
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        active={activeNav}
        onSelect={setActiveNav}
      />

      <main className={styles.main}>
        <Topbar onMenu={() => setSidebarOpen(true)} />
        <MarketStrip />

        <section className={styles.content}>
          <div className={styles.heading}>
            <div><h2>계정 요약</h2><p>2026년 7월 13일 10:44 기준</p></div>
            <div className={styles.actions}>
              <button><Download size={16} /> 리포트 다운로드</button>
              <button className={styles.danger}><Octagon size={16} /> 전체 자동매매 중지</button>
            </div>
          </div>

          <MetricCards />

          <div className={styles.mainGrid}>
            <PerformancePanel />
            <QuickOrder />
          </div>

          <div className={styles.secondaryGrid}>
            <StrategyPanel />
            <RiskPanel />
          </div>

          <OrdersTable />
          <BottomPanels />
        </section>

        <footer className={styles.footer}>
          <span>© 2026 AutoTrade. All rights reserved.</span>
          <div><button>시스템 상태</button><button>도움말</button><button>API 문서</button></div>
        </footer>
      </main>
    </div>
  )
}
