import { useState } from 'react'
import { CheckCircle2, Copy, ExternalLink, Link2, Unlink } from 'lucide-react'
import { apiFetch } from '../../api/client'
import panelStyles from './Panel.module.css'
import styles from './TelegramPanel.module.css'

export default function TelegramPanel({ user, onUserChange }) {
  const [linkInfo, setLinkInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  const refreshUser = async () => {
    setLoading(true)
    setError('')
    try {
      onUserChange(await apiFetch('/users/me'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const createCode = async () => {
    setLoading(true)
    setError('')
    setCopied(false)
    try {
      setLinkInfo(await apiFetch('/users/me/telegram-link-code', { method: 'POST' }))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const unlink = async () => {
    setLoading(true)
    setError('')
    try {
      await apiFetch('/users/me/telegram-link', { method: 'DELETE' })
      setLinkInfo(null)
      onUserChange(await apiFetch('/users/me'))
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  const command = linkInfo ? `/start ${linkInfo.code}` : ''
  const copyCommand = async () => {
    await navigator.clipboard.writeText(command)
    setCopied(true)
  }

  return (
    <article className={panelStyles.panel}>
      <header>
        <div>
          <h3>텔레그램 알림</h3>
          <p>주문 및 전략 실행 결과를 받을 텔레그램 계정을 연결합니다.</p>
        </div>
      </header>

      <div className={styles.content}>
        {user?.telegram_chat_id ? (
          <div className={styles.connected}>
            <span><CheckCircle2 size={18} /><strong>텔레그램 연결됨</strong></span>
            <button className={styles.secondaryButton} onClick={unlink} disabled={loading}>
              <Unlink size={15} /> 연결 해제
            </button>
          </div>
        ) : (
          <>
            {!linkInfo && (
              <div className={styles.start}>
                <span><Link2 size={18} /> 텔레그램 봇과 연결하려면 일회용 코드를 발급하세요.</span>
                <button className={styles.primaryButton} onClick={createCode} disabled={loading}>
                  {loading ? '발급 중...' : '연동 코드 발급'}
                </button>
              </div>
            )}

            {linkInfo && (
              <div className={styles.linkBox}>
                <p>텔레그램 봇 채팅에 아래 명령어를 보내세요. 코드는 10분 동안 유효합니다.</p>
                <div className={styles.command}>
                  <code>{command}</code>
                  <button onClick={copyCommand} aria-label="명령어 복사"><Copy size={16} /></button>
                </div>
                <div className={styles.actions}>
                  {linkInfo.bot_username && (
                    <a href={`https://t.me/${linkInfo.bot_username}`} target="_blank" rel="noreferrer">
                      텔레그램 봇 열기 <ExternalLink size={14} />
                    </a>
                  )}
                  <button onClick={refreshUser} disabled={loading}>연동 확인</button>
                  <button onClick={createCode} disabled={loading}>코드 재발급</button>
                </div>
                {copied && <span className={styles.notice}>명령어를 복사했습니다.</span>}
              </div>
            )}
          </>
        )}

        {error && <p className={styles.error}>{error}</p>}
      </div>
    </article>
  )
}
