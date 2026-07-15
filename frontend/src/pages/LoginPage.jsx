import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle2, Eye, EyeOff, LockKeyhole, ShieldCheck, TrendingUp, UserRound } from 'lucide-react'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const registered = location.state?.registered
  const registeredUserId = location.state?.userId || 'demo_trader'

  const handleSubmit = (event) => {
    event.preventDefault()
    navigate('/dashboard')
  }

  return (
    <main className={styles.shell}>
      <section className={styles.visual}>
        <div className={styles.visualInner}>
          <div className={styles.brand}>
            <span className={styles.brandMark}><TrendingUp size={24} /></span>
            <span>AutoTrade</span>
          </div>

          <div className={styles.copy}>
            <span className={styles.eyebrow}>WEBHOOK-BASED TRADING</span>
            <h1>매매 신호부터 주문 실행까지,<br />한 화면에서 안전하게.</h1>
            <p>
              TradingView 웹훅, 거래소 주문, 전략 상태와 리스크 지표를
              통합 관리하는 암호화폐 자동매매 대시보드입니다.
            </p>
          </div>

          <div className={styles.previewCard}>
            <div className={styles.previewHeader}>
              <div>
                <span>오늘의 누적 수익</span>
                <strong>+₩184,320</strong>
              </div>
              <b>+2.84%</b>
            </div>

            <svg className={styles.chart} viewBox="0 0 520 150" preserveAspectRatio="none">
              <defs>
                <linearGradient id="loginFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6c8cff" stopOpacity=".35" />
                  <stop offset="100%" stopColor="#6c8cff" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path className={styles.grid} d="M0 30H520M0 75H520M0 120H520" />
              <path fill="url(#loginFill)" d="M0 125 C45 118,55 96,95 101 S155 58,200 73 S260 34,308 52 S375 24,420 34 S480 8,520 20 L520 150 L0 150 Z" />
              <path className={styles.line} d="M0 125 C45 118,55 96,95 101 S155 58,200 73 S260 34,308 52 S375 24,420 34 S480 8,520 20" />
            </svg>

            <div className={styles.previewFooter}>
              <span><i /> 자동매매 정상</span>
              <span>최근 동기화 3초 전</span>
            </div>
          </div>

          <div className={styles.features}>
            <div><b>01</b><span><strong>실시간 모니터링</strong><small>주문·체결·손익 상태 확인</small></span></div>
            <div><b>02</b><span><strong>리스크 제어</strong><small>일일 손실 및 주문 한도 관리</small></span></div>
            <div><b>03</b><span><strong>웹훅 연동</strong><small>TradingView 전략 신호 수신</small></span></div>
          </div>
        </div>
      </section>

      <section className={styles.panel}>
        <div className={styles.formWrap}>
          <div className={styles.mobileBrand}>
            <span className={styles.brandMark}><TrendingUp size={24} /></span>
            <strong>AutoTrade</strong>
          </div>

          <div className={styles.heading}>
            <span className={styles.eyebrowDark}>WELCOME BACK</span>
            <h2>계정에 로그인하세요</h2>
            <p>자동매매 시스템을 안전하게 관리할 수 있습니다.</p>
          </div>

          {registered && (
            <div className={styles.successBanner}>
              <CheckCircle2 size={18} />
              <span><strong>회원가입이 완료되었습니다.</strong><small>등록한 아이디로 로그인해 주세요.</small></span>
            </div>
          )}

          <form onSubmit={handleSubmit} className={styles.form}>
            <label>
              <span>아이디</span>
              <div className={styles.inputWrap}>
                <UserRound size={18} />
                <input type="text" defaultValue={registeredUserId} autoComplete="username" required />
              </div>
            </label>

            <label>
              <div className={styles.fieldTop}>
                <span>비밀번호</span>
                <button type="button">비밀번호 찾기</button>
              </div>
              <div className={styles.inputWrap}>
                <LockKeyhole size={18} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  defaultValue="autotrade123"
                  required
                />
                <button
                  type="button"
                  className={styles.eyeButton}
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label="비밀번호 표시 전환"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            <div className={styles.options}>
              <label className={styles.checkbox}>
                <input type="checkbox" defaultChecked />
                <span>로그인 상태 유지</span>
              </label>
              <span className={styles.secure}><ShieldCheck size={15} /> SSL 보안 연결</span>
            </div>

            <button className={styles.loginButton} type="submit">로그인</button>

            <div className={styles.divider}><span>또는</span></div>

            <button className={styles.googleButton} type="button">
              <span className={styles.googleMark}>G</span>
              Google 계정으로 계속하기
            </button>

            <p className={styles.signup}>아직 계정이 없으신가요? <button type="button" onClick={() => navigate('/signup')}>무료로 시작하기</button></p>
          </form>

          <footer className={styles.footer}>
            <span>© 2026 AutoTrade</span>
            <div><button type="button">이용약관</button><button type="button">개인정보처리방침</button></div>
          </footer>
        </div>
      </section>
    </main>
  )
}
