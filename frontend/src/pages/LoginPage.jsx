import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle2, Eye, EyeOff, LockKeyhole, ShieldCheck, TrendingUp, UserRound } from 'lucide-react'
import { API_BASE_URL, saveAccessToken } from '../lib/api'
import styles from './LoginPage.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState(location.state?.userId || '')
  const [password, setPassword] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const registered = location.state?.registered

  const handleSubmit = async (event) => {
    event.preventDefault()
    setErrorMessage('')
    setIsSubmitting(true)
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) {
        throw new Error(data?.detail || '로그인에 실패했습니다.')
      }
      saveAccessToken(data.token.access_token)
      navigate('/dashboard')
    } catch (error) {
      setErrorMessage(error.message)
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
              <path className={styles.line} d="M0 125 C45 118,55 96,95 101 S155