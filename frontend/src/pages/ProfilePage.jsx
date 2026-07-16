import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, CircleAlert, LoaderCircle, PencilLine, UserRound } from 'lucide-react'
import { ApiError, authenticatedFetch, clearAccessToken } from '../lib/api'

export default function ProfilePage() {
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [nickname, setNickname] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState({ type: '', text: '' })

  useEffect(() => {
    let isMounted = true

    async function loadProfile() {
      try {
        const data = await authenticatedFetch('/users/me')
        if (!isMounted) return
        setProfile(data)
        setNickname(data.nickname)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken()
          navigate('/login', { replace: true })
          return
        }
        if (isMounted) setMessage({ type: 'error', text: error.message })
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    loadProfile()
    return () => { isMounted = false }
  }, [navigate])

  const handleSubmit = async (event) => {
    event.preventDefault()
    const nextNickname = nickname.trim()
    if (!nextNickname || nextNickname === profile?.nickname) return

    setIsSaving(true)
    setMessage({ type: '', text: '' })
    try {
      const data = await authenticatedFetch('/users/me', {
        method: 'PATCH',
        body: JSON.stringify({ nickname: nextNickname }),
      })
      setProfile(data)
      setNickname(data.nickname)
      setMessage({ type: 'success', text: '닉네임을 수정했습니다.' })
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return <div style={{ padding: 40 }}><LoaderCircle size={22} /> 프로필을 불러오는 중입니다.</div>
  }

  if (!profile) {
    return <div style={{ padding: 40 }}>프로필을 불러오지 못했습니다.</div>
  }

  return (
    <div style={{ maxWidth: 480, margin: '60px auto', padding: 24 }}>
      <h2>내 프로필</h2>

      {message.text && (
        <div style={{ margin: '12px 0', color: message.type === 'error' ? 'crimson' : 'green' }}>
          {message.type === 'error' ? <CircleAlert size={16} /> : <Check size={16} />}
          {' '}{message.text}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0' }}>
        <UserRound size={32} />
        <div>
          <strong>{profile.nickname}</strong>
          <div style={{ color: '#888' }}>@{profile.username}</div>
        </div>
      </div>

      <form onSubmit={handleSubmit}>
        <label>
          닉네임
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              minLength={2}
              maxLength={12}
              required
            />
            <button type="submit" disabled={isSaving || nickname.trim() === profile.nickname}>
              {isSaving ? '저장 중' : <><PencilLine size={14} /> 수정</>}
            </button>
          </div>
        </label>
      </form>
    </div>
  )
}