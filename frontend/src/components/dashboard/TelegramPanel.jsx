import { useEffect, useState } from 'react'
import { BellRing, CheckCircle2, Copy, ExternalLink, Link2, QrCode, Unlink, X } from 'lucide-react'
import QRCode from 'qrcode'
import { apiFetch } from '../../api/client'
import styles from './TelegramPanel.module.css'

export default function TelegramPanel({ user, onUserChange }) {
  const [linkInfo, setLinkInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const [qrOpen, setQrOpen] = useState(false)
  const [qrImage, setQrImage] = useState('')

  useEffect(() => {
    if (user?.telegram_chat_id) return
    apiFetch('/users/me/telegram-link-code')
      .then(setLinkInfo)
      .catch((requestError) => setError(requestError.message))
  }, [user?.telegram_chat_id])

  useEffect(() => {
    if (!qrOpen || !linkInfo?.bot_username) {
      setQrImage('')
      return
    }
    const botLink = `https://t.me/${linkInfo.bot_username}?start=${linkInfo.code}`
    QRCode.toDataURL(botLink, { width: 300, margin: 4, errorCorrectionLevel: 'M' })
      .then(setQrImage)
      .catch(() => setError('QR 코드를 만들 수 없습니다.'))
  }, [linkInfo, qrOpen])

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
      setQrOpen(false)
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
    <article className={styles.panel}>
      <header className={styles.title}>
        <span><BellRing size={18} /></span>
        <div>
          <h3>텔레그램 알림</h3>
          <p>실전투자와 모의투자의 주문 및 전략 실행 결과를 받을 계정을 연결합니다.</p>
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
                <p>텔레그램 연동이 안 된다면 재발급 버튼을 눌러 다시 연동해 주세요.</p>
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
                  <button onClick={createCode} disabled={loading}>코드 재발급</button>
                  {linkInfo.bot_username && (
                    <button onClick={() => setQrOpen((current) => !current)}>
                      <QrCode size={14} /> QR 보기
                    </button>
                  )}
                  <button onClick={refreshUser} disabled={loading}>연동 확인</button>
                </div>
                {qrOpen && (
                  <div className={styles.qrBox}>
                    <button className={styles.qrClose} onClick={() => setQrOpen(false)} aria-label="QR 코드 닫기"><X size={16} /></button>
                    {qrImage && <img src={qrImage} alt="텔레그램 봇 연동 QR 코드" />}
                    <strong>휴대폰 카메라로 스캔하세요</strong>
                    <span>텔레그램 봇이 열리면 시작 버튼을 눌러 연동을 완료합니다.</span>
                  </div>
                )}
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
