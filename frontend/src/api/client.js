const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TOKEN_KEY = 'autotrade_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function apiFetch(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (response.status === 401) {
    clearToken()
    window.location.href = '/login'
    throw new Error('로그인이 만료되었습니다. 다시 로그인해 주세요.')
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || '요청 처리 중 오류가 발생했습니다.')
  }

  if (response.status === 204) return null
  return response.json()
}

export { API_BASE_URL }
