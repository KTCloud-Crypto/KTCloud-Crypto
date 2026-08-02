import { useEffect, useState } from 'react'
import { FlaskConical, LogOut, ShieldAlert, TrendingUp } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { apiFetch, clearToken } from '../api/client'
import styles from './InvestmentModePage.module.css'

export default function InvestmentModePage() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/users/me').then(setUser).catch((requestError) => setError(requestError.message))
  }, [])

  const enterMode = async (mode) => {
    setLoading(mode)
    setError('')
    try {
      await apiFetch('/users/me', {
        method: 'PUT',
        body: JSON.stringify({ execution_mode: mode }),
      })
      navigate(`/dashboard/${mode}`)
    } catch (requestError) {
      setError(requestError.message)
      setLoading('')
    }
  }

  const logout = () => {
    clearToken()
    navigate('/login', { replace: true })
  }

  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <div className={styles.brand}><TrendingUp size={22} /><strong>SignalTrade</strong></div>
        <div className={styles.user}><span>{user?.nickname || user?.username || ''}</span><button onClick={logout}><LogOut size={16} /> 로그아웃</button></div>
      </header>

      <section className={styles.content}>
        <div className={styles.heading}>
          <span>INVESTMENT MODE</span>
          <h1>어떤 방식으로 시작할까요?</h1>
          <p>모의투자와 실전투자의 전략 설정, 포지션, 실행 내역은 서로 분리되어 관리됩니다.</p>
        </div>

        <div className={styles.cards}>
          <button className={styles.paperCard} onClick={() => enterMode('simulated')} disabled={Boolean(loading)}>
            <span className={styles.icon}><FlaskConical size={28} /></span>
            <span className={styles.cardCopy}><small>연습과 검증</small><strong>모의투자</strong><em>가상 자금으로 전략을 설정하고 수수료·포지션·손익을 확인합니다.</em></span>
            <b>{loading === 'simulated' ? '이동 중...' : '모의투자 시작'}</b>
          </button>

          <button className={styles.liveCard} onClick={() => enterMode('live')} disabled={Boolean(loading)}>
            <span className={styles.icon}><ShieldAlert size={28} /></span>
            <span className={styles.cardCopy}><small>Upbit 실제 주문</small><strong>실전투자</strong><em>실제 자산을 사용하는 별도의 전략 설정과 체결 내역을 관리합니다.</em></span>
            <b>{loading === 'live' ? '이동 중...' : '실전투자 시작'}</b>
          </button>
        </div>
        {error && <p className={styles.error}>{error}</p>}
      </section>
    </main>
  )
}
