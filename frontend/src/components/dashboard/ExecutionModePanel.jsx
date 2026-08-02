import { useState } from 'react'
import { FlaskConical, ShieldAlert } from 'lucide-react'
import { apiFetch } from '../../api/client'
import panelStyles from './Panel.module.css'
import styles from './ExecutionModePanel.module.css'

export default function ExecutionModePanel({ user, onUserChange }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const changeMode = async (executionMode) => {
    setSaving(true)
    setError('')
    try {
      const updatedUser = await apiFetch('/users/me', {
        method: 'PUT',
        body: JSON.stringify({ execution_mode: executionMode }),
      })
      onUserChange(updatedUser)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setSaving(false)
    }
  }

  const mode = user?.execution_mode || 'simulated'

  return (
    <article className={panelStyles.panel}>
      <header>
        <div>
          <h3>주문 실행 모드</h3>
          <p>전략 신호가 발생했을 때 사용할 실행 방식을 선택합니다.</p>
        </div>
      </header>

      <div className={styles.content}>
        <button
          className={mode === 'simulated' ? styles.selected : styles.option}
          onClick={() => changeMode('simulated')}
          disabled={saving || !user}
        >
          <FlaskConical size={19} />
          <span><strong>모의 실행</strong><small>모의계좌 잔고로 수수료와 전략별 포지션을 반영해 가상 체결합니다.</small></span>
        </button>
        <button
          className={mode === 'live' ? styles.liveSelected : styles.option}
          onClick={() => changeMode('live')}
          disabled={saving || !user}
        >
          <ShieldAlert size={19} />
          <span><strong>실전 실행</strong><small>전역 실전매매 스위치가 활성화되면 실제 Upbit 주문을 실행합니다.</small></span>
        </button>
        {error && <p className={styles.error}>{error}</p>}
      </div>
    </article>
  )
}
