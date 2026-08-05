import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, LineChart } from 'lucide-react'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import { apiFetch, clearToken } from '../api/client'
import { serviceReadiness } from '../utils/serviceReadiness'
import layoutStyles from './DashboardPage.module.css'
import styles from './StrategyGuidePage.module.css'

const STRATEGIES = [
  {
    code: 'sma_cross_v1',
    name: '이동평균 교차 전략',
    oneLiner: '가격의 최근 흐름과 조금 더 긴 흐름을 비교해, 방향이 바뀌는 순간을 잡아냅니다.',
    buy: '최근 5분 동안의 평균 가격이 최근 20분 동안의 평균 가격을 아래에서 위로 뚫고 올라가면 매수합니다. "단기적으로 분위기가 좋아지기 시작했다"는 신호로 봅니다.',
    sell: '반대로 5분 평균이 20분 평균을 위에서 아래로 뚫고 내려가면 매도합니다.',
    goodFor: '가격이 한 방향으로 꾸준히 움직이는 추세장',
    badFor: '가격이 좁은 범위에서 계속 왔다갔다 하는 횡보장 (신호가 자주 틀릴 수 있습니다)',
    beginnerNote: '가장 기본적이고 이해하기 쉬운 전략입니다. 처음 자동매매를 시작하신다면 이 전략으로 모의투자를 먼저 해보시길 권장합니다.',
  },
  {
    code: 'rsi_reversal_v1',
    name: 'RSI 과매수·과매도 반전',
    oneLiner: '"너무 많이 떨어졌다" 싶을 때 사고, "너무 많이 올랐다" 싶을 때 파는 전략입니다.',
    buy: 'RSI라는 지표(0~100 사이 값으로 최근 상승/하락 강도를 나타냄)가 30 아래로 떨어졌다가 다시 30 위로 올라오면 매수합니다. "바닥을 찍고 반등하기 시작했다"는 신호입니다.',
    sell: 'RSI가 70 위로 올라갔다가 다시 70 아래로 내려오면 매도합니다. "고점을 찍고 꺾이기 시작했다"는 신호입니다.',
    goodFor: '가격이 일정 범위 안에서 오르내리는 횡보장',
    badFor: '한쪽 방향으로 계속 밀고 나가는 강한 추세장 (계속 오르는데 "너무 올랐다"며 일찍 매도할 수 있습니다)',
    beginnerNote: '"쌀 때 사서 비쌀 때 판다"는 직관과 잘 맞아 이해하기 쉬운 편입니다.',
  },
  {
    code: 'macd_cross_v1',
    name: 'MACD 크로스',
    oneLiner: '이동평균 교차 전략의 조금 더 정교한 버전입니다.',
    buy: '단기 추세선(MACD)이 그 흐름을 부드럽게 만든 기준선(시그널선)을 아래에서 위로 뚫고 올라가면 매수합니다.',
    sell: 'MACD가 시그널선을 위에서 아래로 뚫고 내려가면 매도합니다.',
    goodFor: '가격이 한 방향으로 꾸준히 움직이는 추세장',
    badFor: '횡보장에서는 신호가 자주 어긋날 수 있습니다',
    beginnerNote: '이동평균 교차와 원리는 비슷하지만 계산 방식이 조금 더 복잡해서, 왜 이 시점에 신호가 났는지 직관적으로 이해하기는 다소 어려울 수 있습니다.',
  },
  {
    code: 'bollinger_reentry_v1',
    name: '볼린저 밴드 회귀',
    oneLiner: '가격이 평소보다 크게 벗어났다가 다시 정상 범위로 돌아오는 순간을 노립니다.',
    buy: '가격이 평소 변동 범위(밴드)의 아래쪽 경계를 벗어났다가 다시 범위 안으로 들어오면 매수합니다.',
    sell: '가격이 위쪽 경계를 벗어났다가 다시 범위 안으로 들어오면 매도합니다.',
    goodFor: '횡보장, 그리고 급등락 이후 안정을 찾아가는 구간',
    badFor: '변동성이 계속 커지며 밴드를 뚫고 나가는 강한 추세장',
    beginnerNote: 'RSI 반전 전략과 비슷한 성격이지만, "가격이 평소보다 얼마나 벗어났는지"를 기준으로 삼는다는 점이 다릅니다.',
  },
  {
    code: 'donchian_breakout_v1',
    name: '돈치안 채널 돌파',
    oneLiner: '최근에 없던 새로운 고점이나 저점이 나오면 그 흐름에 올라타는 전략입니다.',
    buy: '현재 가격이 최근 20개 캔들 중 가장 높았던 가격을 넘어서면 매수합니다. "신고가 경신"을 상승 시작 신호로 봅니다.',
    sell: '현재 가격이 최근 20개 캔들 중 가장 낮았던 가격 아래로 떨어지면 매도합니다.',
    goodFor: '강한 상승이나 하락이 새로 시작되는 돌파 구간',
    badFor: '박스권에서 오르내리기만 하는 횡보장 (거짓 돌파에 속아 잦은 매매가 발생할 수 있습니다)',
    beginnerNote: '"오르는 놈이 계속 오른다"는 추세추종형 전략입니다. 신고가/신저가라는 개념만 이해하면 직관적입니다.',
  },
]

export default function StrategyGuidePage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [expandedCode, setExpandedCode] = useState(STRATEGIES[0].code)
  const [user, setUser] = useState(null)

  useEffect(() => {
    apiFetch('/users/me').then(setUser).catch(() => {})
  }, [])

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <div className={layoutStyles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout} />
      <main className={layoutStyles.main}>
        <Topbar
          onMenu={() => setSidebarOpen(true)}
          user={user}
          title="전략 알아보기"
          subtitle="5개 전략이 각각 어떤 원리로 매수·매도하는지 확인하세요."
          readiness={serviceReadiness(user)}
        />
        <section className={`${layoutStyles.content} ${styles.content}`}>
          <div className={styles.list}>
            {STRATEGIES.map((strategy) => {
              const expanded = expandedCode === strategy.code
              return (
                <article key={strategy.code} className={styles.card}>
                  <button
                    className={styles.cardHeader}
                    onClick={() => setExpandedCode(expanded ? null : strategy.code)}
                    aria-expanded={expanded}
                  >
                    <span className={styles.cardIcon}><LineChart size={20} /></span>
                    <span className={styles.cardHeaderText}>
                      <strong>{strategy.name}</strong>
                      <small>{strategy.oneLiner}</small>
                    </span>
                    <ChevronDown className={expanded ? styles.chevronOpen : ''} size={18} />
                  </button>

                  {expanded && (
                    <div className={styles.cardBody}>
                      <div className={styles.row}>
                        <span className={styles.buyTag}>매수 조건</span>
                        <p>{strategy.buy}</p>
                      </div>
                      <div className={styles.row}>
                        <span className={styles.sellTag}>매도 조건</span>
                        <p>{strategy.sell}</p>
                      </div>
                      <div className={styles.fitGrid}>
                        <div className={styles.fitGood}>
                          <small>이런 시장에 적합해요</small>
                          <p>{strategy.goodFor}</p>
                        </div>
                        <div className={styles.fitBad}>
                          <small>이런 시장은 조심하세요</small>
                          <p>{strategy.badFor}</p>
                        </div>
                      </div>
                      <p className={styles.beginnerNote}>{strategy.beginnerNote}</p>
                    </div>
                  )}
                </article>
              )
            })}
          </div>

          <div className={styles.ctaRow}>
            <button className={styles.ctaPrimary} onClick={() => navigate('/dashboard/simulated')}>
              모의투자에서 직접 구독해 보기
            </button>
          </div>
        </section>
      </main>
    </div>
  )
}
