import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { KeyRound, LockKeyhole, Send, ShieldCheck, UserRound } from 'lucide-react'
import { apiFetch } from '../api/client'
import styles from './LoginPage.module.css'

export default function PasswordResetPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState('request')
  const [username, setUsername] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [commandCopied, setCommandCopied] = useState(false)

  const copyFindIdCommand = async () => {
    try {
      await navigator.clipboard.writeText('/findid')
      setCommandCopied(true)
    } catch {
      setError('명령어를 복사하지 못했습니다. /findid를 직접 입력해 주세요.')
    }
  }

  const requestToken = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const data = await apiFetch('/auth/password-reset/request', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim() }),
        skipAuthRedirect: true,
      })
      setMessage(data.message)
      setStep('confirm')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const resetPassword = async (event) => {
    event.preventDefault()
    setError('')
    if (newPassword !== confirmPassword) {
      setError('새 비밀번호 확인이 일치하지 않습니다.')
      return
    }
    setBusy(true)
    try {
      const data = await apiFetch('/auth/password-reset/confirm', {
        method: 'POST',
        body: JSON.stringify({ username: username.trim(), token, new_password: newPassword }),
        skipAuthRedirect: true,
      })
      navigate('/login', { replace: true, state: { message: data.message } })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className={styles.shell}>
      <section className={styles.visual}>
        <div className={styles.visualInner}>
          <div className={styles.brand}><span>SignalTrade</span></div>
          <div className={styles.copy}>
            <span className={styles.eyebrow}>SECURE ACCOUNT RECOVERY</span>
            <h1>텔레그램으로 안전하게<br />계정을 복구하세요.</h1>
            <p>연결된 텔레그램으로 전송된 일회용 코드는 3분 동안만 사용할 수 있습니다.</p>
          </div>
        </div>
      </section>
      <section className={styles.panel}>
        <div className={styles.formWrap}>
          <div className={styles.heading}>
            <span className={styles.eyebrowDark}>PASSWORD RESET</span>
            <h2>비밀번호 재설정</h2>
            <p>{step === 'request' ? '텔레그램이 연결된 계정의 아이디를 입력하세요.' : '텔레그램으로 받은 8자리 코드를 입력하세요.'}</p>
          </div>

          {message && <div className={styles.successBanner}><ShieldCheck size={18} /><span><strong>코드 요청 완료</strong><small>{message}</small></span></div>}
          {error && <div className={styles.formErrorWrap} role="alert"><p className={styles.formError}>{error}</p></div>}

          {step === 'request' && (
            <div className={styles.successBanner}>
              <KeyRound size={18} />
              <span>
                <strong>아이디를 잊으셨나요?</strong>
                <small>연결된 텔레그램 봇의 개인 채팅에 아래 명령어를 입력하세요.</small>
                <button type="button" className={styles.commandCopyButton} onClick={copyFindIdCommand}>
                  /findid <span>{commandCopied ? '복사 완료' : '복사'}</span>
                </button>
              </span>
            </div>
          )}

          <form className={styles.form} onSubmit={step === 'request' ? requestToken : resetPassword}>
            <label><span>아이디</span><div className={styles.inputWrap}><UserRound size={18} /><input value={username} onChange={(e) => setUsername(e.target.value)} disabled={step === 'confirm'} required autoComplete="username" /></div></label>
            {step === 'confirm' && <>
              <label><span>8자리 인증 코드</span><div className={styles.inputWrap}><KeyRound size={18} /><input value={token} onChange={(e) => setToken(e.target.value.replace(/\D/g, '').slice(0, 8))} inputMode="numeric" pattern="[0-9]{8}" required autoComplete="one-time-code" /></div></label>
              <label><span>새 비밀번호</span><div className={styles.inputWrap}><LockKeyhole size={18} /><input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} minLength={8} maxLength={32} required autoComplete="new-password" /></div></label>
              <label><span>새 비밀번호 확인</span><div className={styles.inputWrap}><LockKeyhole size={18} /><input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} minLength={8} maxLength={32} required autoComplete="new-password" /></div></label>
            </>}
            <button className={styles.loginButton} type="submit" disabled={busy}>{busy ? '처리 중...' : step === 'request' ? <><Send size={16} /> 인증 코드 받기</> : '비밀번호 변경'}</button>
            {step === 'confirm' && <p className={styles.signup}>코드를 못 받으셨나요? <button type="button" onClick={() => { setStep('request'); setMessage(''); setToken('') }}>다시 요청하기</button></p>}
            <p className={styles.signup}><button type="button" onClick={() => navigate('/login')}>로그인으로 돌아가기</button></p>
          </form>
        </div>
      </section>
    </main>
  )
}
