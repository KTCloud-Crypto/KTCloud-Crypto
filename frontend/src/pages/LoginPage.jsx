import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle2, Eye, EyeOff, LockKeyhole, ShieldCheck, TrendingUp, UserRound } from 'lucide-react'
import { apiFetch, setToken } from '../api/client'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState(location.state?.userId || '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const registered = location.state?.registered

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (!username.trim() || !password) {
      setError('아이디와 비밀번호를 모두 입력해 주세요.')
      return
    }

    setError('')
    setIsSubmitting(true)

    try {
      const data = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
        skipAuthRedirect: true,
      })
      setToken(data.token.access_token)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const response = err?.response || {}
      setError(response.detail || err?.message || '로그인에 실패했습니다.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className={styles.shell}>
      <section className={styles.visual}>
        <div className={styles.visualInner}>
          <div className={styles.brand}>
            <span className={styles.brandMark}><TrendingUp size={24} /></span>
            <span>SignalTrade</span>
          </div>

          <div className={styles.copy}>
            <span className={styles.eyebrow}>UPBIT API-BASED TRADING</span>
            <h1>매매 신호부터 주문 실행까지,<br />한 화면에서 안전하게.</h1>
            <p>
              Upbit 실시간 시세와 선택한 전략을 기반으로
              자동매매를 실행하고 거래 결과를 관리합니다.
            </p>
          </div>
        </div>
      </section>

      <section className={styles.panel}>
        <div className={styles.formWrap}>
          <div className={styles.mobileBrand}>
            <span className={styles.brandMark}><TrendingUp size={24} /></span>
            <strong>SignalTrade</strong>
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
                <input
                  type="text"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  required
                  spellCheck={false}
                />
              </div>
            </label>

            <label>
              <div className={styles.fieldTop}>
                <span>비밀번호</span>
              </div>
              <div className={styles.inputWrap}>
                <LockKeyhole size={18} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  required
                  spellCheck={false}
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
              <span className={styles.secure}><ShieldCheck size={15} /> SSL 보안 연결</span>
            </div>

            {error && (
              <div className={styles.formErrorWrap} role="alert">
                <p className={styles.formError}>{error}</p>
              </div>
            )}

            <button className={styles.loginButton} type="submit" disabled={isSubmitting}>
              {isSubmitting ? '로그인 중...' : '로그인'}
            </button>

            <p className={styles.signup}>아직 계정이 없으신가요? <button type="button" onClick={() => navigate('/signup')}>무료로 시작하기</button></p>
          </form>

          <footer className={styles.footer}>
            <span>© 2026 SignalTrade</span>
          </footer>
        </div>
      </section>
    </main>
  )
}
