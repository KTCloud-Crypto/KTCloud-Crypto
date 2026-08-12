import { serviceReadiness } from '../utils/serviceReadiness'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, KeyRound, ShieldCheck, UserRound } from 'lucide-react'
import Sidebar from '../components/layout/Sidebar'
import Topbar from '../components/layout/Topbar'
import TelegramPanel from '../components/dashboard/TelegramPanel'
import { apiFetch, clearToken } from '../api/client'
import layoutStyles from './DashboardPage.module.css'
import styles from './SettingsPage.module.css'

const emptyPassword = { current_password: '', new_password: '', confirm: '' }

export default function SettingsPage() {
  const [searchParams] = useSearchParams()
  const highlightTelegram = searchParams.get('highlight') === 'telegram'
  const highlightLive = searchParams.get('highlight') === 'live'
  const highlightApi = searchParams.get('highlight') === 'api'
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState(null)
  const [accountStatus, setAccountStatus] = useState(null)
  const [profile, setProfile] = useState({ nickname: '' })
  const [liveTradingEnabled, setLiveTradingEnabled] = useState(false)
  const [password, setPassword] = useState(emptyPassword)
  const [keys, setKeys] = useState({ access_key: '', secret_key: '' })
  const [keyDeletePassword, setKeyDeletePassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const apiKeyConnected = accountStatus?.api_key_registered && accountStatus?.api_key_valid === true

  useEffect(() => {
    apiFetch('/users/me')
      .then((me) => {
        setUser(me)
        setProfile({ nickname: me.nickname })
        setLiveTradingEnabled(me.live_trading_enabled || false)
      })
      .catch((err) => setError(err.message))
    apiFetch('/users/me/status')
      .then(setAccountStatus)
      .catch((err) => setError(err.message))
  }, [])

  const run = async (name, work, success) => {
    setBusy(name); setError(''); setMessage('')
    try {
      await work()
      setMessage(success)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const logout = () => { clearToken(); navigate('/login', { replace: true }) }

  const saveProfile = (event) => {
    event.preventDefault()
    run('profile', async () => {
      const updated = await apiFetch('/users/me', {
        method: 'PUT',
        body: JSON.stringify(profile),
      })
      setUser(updated)
      setProfile({ nickname: updated.nickname })
    }, '회원정보를 수정했습니다.')
  }

  const toggleLiveTrading = async () => {
    const newValue = !liveTradingEnabled
    if (newValue && !window.confirm('⚠️ 실전투자를 활성화하시겠습니까?\n\n활성화 시 연결된 Upbit 계좌에서 전략에 따라\n실제 매수/매도 주문이 자동으로 실행됩니다.')) {
      return
    }
    run('live-trading', async () => {
      const updated = await apiFetch('/users/me', {
        method: 'PUT',
        body: JSON.stringify({ live_trading_enabled: newValue }),
      })
      setUser(updated)
      setLiveTradingEnabled(updated.live_trading_enabled)
    }, newValue ? '실전투자가 활성화되었습니다.' : '실전투자가 비활성화되었습니다.')
  }

  const changePassword = (event) => {
    event.preventDefault()
    if (password.new_password !== password.confirm) return setError('새 비밀번호 확인이 일치하지 않습니다.')
    run('password', async () => {
      await apiFetch('/users/me/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: password.current_password, new_password: password.new_password }),
      })
      setPassword(emptyPassword)
      clearToken()
      navigate('/login', { replace: true, state: { message: '비밀번호가 변경되었습니다. 다시 로그인해 주세요.' } })
    }, '')
  }

  const saveKeys = (event) => {
    event.preventDefault()
    run('keys', async () => {
      await apiFetch('/users/me/exchange-key', { method: 'POST', body: JSON.stringify(keys) })
      setKeys({ access_key: '', secret_key: '' })
      setAccountStatus(await apiFetch('/users/me/status'))
      setUser(await apiFetch('/users/me'))
    }, 'Upbit API 키를 검증하고 암호화해 저장했습니다.')
  }

  const removeKeys = () => {
    if (!window.confirm('저장된 거래소 키를 삭제하고 자동매매를 중지할까요?')) return
    run('key-delete', async () => {
      await apiFetch('/users/me/exchange-key', { method: 'DELETE', body: JSON.stringify({ password: keyDeletePassword }) })
      setKeyDeletePassword('')
      setAccountStatus(await apiFetch('/users/me/status'))
      setUser(await apiFetch('/users/me'))
    }, '저장된 거래소 API 키를 삭제했습니다.')
  }

  return (
    <div className={layoutStyles.app}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} user={user} onLogout={logout}
        activePage="settings" />
      <main className={layoutStyles.main}>
        <Topbar
          onMenu={() => setSidebarOpen(true)}
          user={user}
          title="계정 설정"
          subtitle="회원정보와 외부 서비스 연결을 관리합니다."
          readiness={serviceReadiness(user)}
        />
        <section className={`${layoutStyles.content} ${styles.content}`}>
          <div className={styles.heading}><div><h2>계정 및 보안</h2><p>민감정보는 화면에 다시 표시하지 않습니다.</p></div></div>
          {message && <p className={styles.success}><CheckCircle2 size={16} />{message}</p>}
          {error && <p className={styles.error}>{error}</p>}

          <div className={styles.grid}>
            <form className={styles.card} onSubmit={saveProfile}>
              <CardTitle icon={UserRound} title="회원정보" description="화면에 표시되는 닉네임을 변경합니다." />
              <Field label="아이디"><input value={user?.username || ''} disabled /></Field>
              <Field label="닉네임"><input required minLength="2" maxLength="12" value={profile.nickname} onChange={(e) => setProfile({ ...profile, nickname: e.target.value })} /></Field>
              <div
                className={highlightLive ? styles.telegramHighlight : ''}
                ref={(node) => { if (node && highlightLive) node.scrollIntoView({ behavior: 'smooth', block: 'center' }) }}
              >
                <Field label="실전투자">
                  <div className={styles.toggleField}>
                    <label className={styles.toggle}>
                      <input type="checkbox" checked={liveTradingEnabled} onChange={toggleLiveTrading} disabled={!user || busy === 'live-trading'} />
                      <span className={styles.slider}></span>
                    </label>
                    <span className={liveTradingEnabled ? styles.activeText : styles.inactiveText}>
                      {liveTradingEnabled ? '활성화됨' : '비활성화됨'}
                    </span>
                  </div>
                </Field>
              </div>
              <button className={`${styles.primary} ${styles.bottomAction}`} disabled={busy === 'profile'}>{busy === 'profile' ? '저장 중...' : '회원정보 저장'}</button>
            </form>

            <form className={styles.card} onSubmit={changePassword}>
              <CardTitle icon={ShieldCheck} title="비밀번호 변경" description="영문과 숫자를 포함한 8~32자를 사용하세요." />
              <Field label="현재 비밀번호"><input type="password" autoComplete="current-password" required minLength="8" value={password.current_password} onChange={(e) => setPassword({ ...password, current_password: e.target.value })} /></Field>
              <Field label="새 비밀번호"><input type="password" autoComplete="new-password" required minLength="8" value={password.new_password} onChange={(e) => setPassword({ ...password, new_password: e.target.value })} /></Field>
              <Field label="새 비밀번호 확인"><input type="password" autoComplete="new-password" required minLength="8" value={password.confirm} onChange={(e) => setPassword({ ...password, confirm: e.target.value })} /></Field>
              <button className={`${styles.primary} ${styles.bottomAction}`} disabled={busy === 'password'}>{busy === 'password' ? '변경 중...' : '비밀번호 변경'}</button>
            </form>

            <form
              className={`${styles.card} ${highlightApi ? styles.telegramHighlight : ''}`}
              onSubmit={saveKeys}
              ref={(node) => { if (node && highlightApi) node.scrollIntoView({ behavior: 'smooth', block: 'center' }) }}
            >
              <CardTitle icon={KeyRound} title="Upbit API 연결" description="등록 전에 Upbit에서 유효성을 확인하며, 키는 암호화 저장됩니다." />
              <p className={apiKeyConnected ? styles.connected : styles.disconnected}>
                {accountStatus === null
                  ? '연결 상태 확인 중...'
                  : !accountStatus.api_key_registered
                  ? '연결되지 않음'
                  : apiKeyConnected ? '연결 정상' : '연결 오류'}
              </p>
              {accountStatus?.api_key_registered && accountStatus?.api_key_valid === false && (
                <p className={styles.keyStatusError}>{accountStatus.api_key_status_message}</p>
              )}
              <Field label="Access Key"><input type="password" autoComplete="off" required minLength="10" value={keys.access_key} onChange={(e) => setKeys({ ...keys, access_key: e.target.value })} /></Field>
              <Field label="Secret Key"><input type="password" autoComplete="off" required minLength="10" value={keys.secret_key} onChange={(e) => setKeys({ ...keys, secret_key: e.target.value })} /></Field>
              <button className={styles.primary} disabled={busy === 'keys'}>{busy === 'keys' ? '검증 중...' : 'API 키 검증 및 저장'}</button>
              {accountStatus?.api_key_registered && <div className={styles.inlineDanger}><input type="password" placeholder="해제할 계정 비밀번호" value={keyDeletePassword} onChange={(e) => setKeyDeletePassword(e.target.value)} /><button type="button" disabled={keyDeletePassword.length < 8 || busy === 'key-delete'} onClick={removeKeys}>연결 해제</button></div>}
            </form>

            <div
              className={`${styles.telegramCard} ${highlightTelegram ? styles.telegramHighlight : ''}`}
              ref={(node) => { if (node && highlightTelegram) node.scrollIntoView({ behavior: 'smooth', block: 'center' }) }}
            >
              <TelegramPanel user={user} onUserChange={setUser} />
            </div>
          </div>

        </section>
      </main>
    </div>
  )
}

function CardTitle({ icon: Icon, title, description }) {
  return <div className={styles.cardTitle}><span><Icon size={18} /></span><div><h3>{title}</h3><p>{description}</p></div></div>
}

function Field({ label, children }) {
  return <label className={styles.field}><span>{label}</span>{children}</label>
}
