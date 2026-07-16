import { useEffect, useState } from 'react'
import { Copy, Check } from 'lucide-react'
import { apiFetch, API_BASE_URL } from '../../api/client'
import panelStyles from './Panel.module.css'
import styles from './WebhookPanel.module.css'

export default function WebhookPanel({ user, onUserChange }) {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/users/me/webhook-url')
      .then((data) => setWebhookUrl(`${API_BASE_URL}${data.webhook_path}`))
      .catch((err) => setError(err.message))
  }, [])

  const handleCopy = async () => {
    if (!webhookUrl) return
    await navigator.clipboard.writeText(webhookUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const toggleBot = async () => {
    if (!user) return
    try {
      const updated = await apiFetch('/users/me', {
        method: 'PUT',
        body: JSON.stringify({ bot_enabled: !user.bot_enabled }),
      })
      onUserChange(updated)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <article className={panelStyles.panel}>
      <header>
        <div>
          <h3>TradingView 웹훅</h3>
          <p>내 전용 웹훅 URL</p>
        </div>
      </header>

      <div className={styles.body}>
        {error && <p>{error}</p>}
        {!error && (
          <div className={styles.urlRow}>
            <code>{webhookUrl || '불러오는 중...'}</code>
            <button onClick={handleCopy} disabled={!webhookUrl}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? '복사됨' : '복사'}
            </button>
          </div>
        )}
        <p className={styles.hint}>TradingView 알림 웹훅 URL로 이 주소를 등록하세요.</p>

        {user && (
          <div className={styles.toggleRow}>
            <span>자동매매 신호 수신</span>
            <button className={user.bot_enabled ? styles.on : styles.off} onClick={toggleBot}>
              {user.bot_enabled ? '켜짐' : '꺼짐'}
            </button>
          </div>
        )}
      </div>
    </article>
  )
}
