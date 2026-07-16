import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import styles from './Panel.module.css'

export default function PositionsPanel() {
  const [positions, setPositions] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/positions')
      .then(setPositions)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <article className={styles.panel}>
      <header>
        <div>
          <h3>매매 포지션</h3>
          <p>웹훅으로 실행된 매수/매도 결과 (DB 기록)</p>
        </div>
      </header>

      {error && <div className={styles.empty}>{error}</div>}

      {!error && (
        <div className={styles.scroll}>
          <table>
            <thead><tr><th>종목</th><th>상태</th><th>갱신 시각</th></tr></thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.id}>
                  <td><strong>{position.ticker}</strong></td>
                  <td><span className={position.status === 'long' ? styles.long : styles.flat}>{position.status === 'long' ? '보유 중' : '없음'}</span></td>
                  <td>{new Date(position.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {positions.length === 0 && <div className={styles.empty}>기록된 포지션이 없습니다.</div>}
        </div>
      )}
    </article>
  )
}
