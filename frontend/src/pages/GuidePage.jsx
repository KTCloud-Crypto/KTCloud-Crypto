import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  BellRing,
  ChevronDown,
  CircleDollarSign,
  FlaskConical,
  KeyRound,
  Layers3,
  ShieldAlert,
} from 'lucide-react'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import { apiFetch, clearToken } from '../api/client'
import { serviceReadiness } from '../utils/serviceReadiness'
import layoutStyles from './DashboardPage.module.css'
import styles from './GuidePage.module.css'

const STEPS = [
  {
    icon: BellRing,
    step: 1,
    title: '텔레그램 알림 먼저 연결하기',
    body: (
      <>
        <strong>계정 설정</strong>에서 텔레그램 연동 코드를 발급받아 봇에 전송하면,{' '}
        <strong>매수·매도 체결 결과를 실시간으로 알림</strong> 받을 수 있습니다. 자동매매는
        사람이 계속 화면을 보고 있지 않아도 동작하므로, 알림을 먼저 켜두면 무슨 일이
        일어나는지 놓치지 않을 수 있습니다.
      </>
    ),
    ctas: [{ label: '텔레그램 연결하러 가기', to: '/settings?highlight=telegram' }],
  },
  {
    icon: FlaskConical,
    step: 2,
    title: '모의투자로 먼저 연습하기',
    body: (
      <>
        <strong>실제 돈이 오가지 않는 가상 계좌</strong>입니다. 원하는 만큼 가상 잔고를
        입금하고, 전략을 구독해 어떻게 매매되는지 먼저 확인해 보세요.
      </>
    ),
    ctas: [{ label: '모의투자로 이동', to: '/dashboard/simulated' }],
  },
  {
    icon: Layers3,
    step: 3,
    title: '전략 구독하기',
    body: (
      <>
        모의투자 또는 실전투자 화면에서 <strong>"새 전략 추가하기"</strong> 버튼을 누르면,
        종목 선택 → 전략 선택 → 예산 설정 → 확인 순서로 안내해 드립니다. 어떤 전략을
        골라야 할지 모르겠다면 전략 알아보기에서 5개 전략을 하나씩 자세히 확인해 보세요.
      </>
    ),
    linkLabel: '전략 알아보기',
    linkTo: '/guide/strategies',
  },
  {
    icon: CircleDollarSign,
    step: 4,
    title: '주문 예산 이해하기',
    body: (
      <>
        전략을 <strong>구독하는 시점의 주문 가능 현금</strong>을 기준으로 예산이 정해집니다.
        비율(%)이나 금액(원) 중 편한 방식으로 입력할 수 있고,{' '}
        <strong>최소 주문 금액은 5,000원</strong>입니다. 매도가 체결되면 회수한 금액이 다음
        매수 예산이 됩니다.
      </>
    ),
  },
  {
    icon: KeyRound,
    step: 5,
    title: '실전투자로 전환하기',
    body: (
      <>
        <strong>회원가입 시 등록하신 Upbit API 키가 이미 연결</strong>되어 있지만,{' '}
        <strong>계정 설정에서 "실전투자" 토글을 반드시 켜야</strong> 실제 주문이 실행됩니다.
        토글이 꺼진 채로 전략을 구독하면 검증만 하고 실제 매매는 나가지 않습니다. 모의투자로
        충분히 검증한 전략이 있다면, 토글을 켠 뒤 실전투자 화면에서 그대로 구독하면
        자동매매가 시작됩니다.
      </>
    ),
    ctas: [
      { label: '실전투자 토글 활성화하기', to: '/settings?highlight=live' },
      { label: '실전투자로 이동', to: '/dashboard/live' },
    ],
  },
  {
    icon: ShieldAlert,
    step: 6,
    title: '위험 관리하기',
    body: (
      <>
        각 전략 설정에서 <strong>손절률과 목표 수익률</strong>을 정해두면, 보유 포지션의
        평균 매수가를 기준으로 자동 매도됩니다. 급할 때는{' '}
        <strong>"보유 포지션 전량 매도"</strong> 버튼으로 모든 포지션을 한 번에 정리할 수
        있습니다.
      </>
    ),
  },
]

export default function GuidePage() {
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [openStep, setOpenStep] = useState(1)

  useEffect(() => {
    apiFetch('/users/me').then(setUser).catch(() => {})
  }, [])

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  const toggleStep = (step) => {
    setOpenStep((current) => (current === step ? null : step))
  }

  return (
    <div className={layoutStyles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout} />
      <main className={layoutStyles.main}>
        <Topbar
          onMenu={() => setSidebarOpen(true)}
          user={user}
          title="이용 가이드"
          subtitle="아래 순서대로 하나씩 진행해 보세요."
          readiness={serviceReadiness(user)}
        />
        <section className={`${layoutStyles.content} ${styles.content}`}>
          <div className={styles.steps}>
            {STEPS.map((step) => {
              const Icon = step.icon
              const expanded = openStep === step.step
              return (
                <article key={step.title} className={`${styles.stepCard} ${expanded ? styles.stepCardOpen : ''}`}>
                  <div className={styles.stepHeader}>
                    <button
                      type="button"
                      className={styles.stepHeaderMain}
                      onClick={() => toggleStep(step.step)}
                      aria-expanded={expanded}
                    >
                      <span className={styles.stepIcon}><Icon size={20} /></span>
                      <span className={styles.stepHeaderText}>
                        <span className={styles.stepBadge}>STEP {step.step}</span>
                        <strong>{step.title}</strong>
                      </span>
                    </button>

                    <div className={styles.stepHeaderActions}>
                      {step.ctas?.map((cta) => (
                        <button
                          key={cta.label}
                          type="button"
                          className={styles.ctaChip}
                          onClick={(event) => {
                            event.stopPropagation()
                            navigate(cta.to)
                          }}
                        >
                          {cta.label} <ArrowRight size={13} />
                        </button>
                      ))}
                      <button
                        type="button"
                        className={styles.expandToggle}
                        onClick={() => toggleStep(step.step)}
                        aria-label={expanded ? '접기' : '펼치기'}
                      >
                        <ChevronDown className={expanded ? styles.chevronOpen : ''} size={18} />
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className={styles.stepBody}>
                      <p>{step.body}</p>
                      {step.linkTo && (
                        <button className={styles.stepLink} onClick={() => navigate(step.linkTo)}>
                          {step.linkLabel} <ArrowRight size={14} />
                        </button>
                      )}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </section>
      </main>
    </div>
  )
}