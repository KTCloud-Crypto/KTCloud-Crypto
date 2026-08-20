const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TOKEN_KEY = 'signaltrade_token'
let redirectingToLogin = false

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

function redirectToLogin() {
  if (redirectingToLogin) return
  redirectingToLogin = true
  clearToken()

  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  } else {
    window.history.replaceState({}, '', '/login')
  }
}

export async function apiFetch(path, options = {}) {
  // 로그인 이후 API는 저장된 JWT를 자동으로 Authorization 헤더에 포함합니다.
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  // 로그인 페이지가 아닌 곳에서 401이 발생하면 자동으로 로그인 페이지로 이동
  // skipAuthRedirect 옵션이 true면 자동 리다이렉트 하지 않음
  if (response.status === 401 && !options.skipAuthRedirect) {
    redirectToLogin()
    throw new Error('로그인이 만료되었습니다. 다시 로그인해 주세요.')
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))

    // detail이 배열인 경우 (Pydantic 유효성 검사 에러)
    if (Array.isArray(data.detail)) {
      const messages = data.detail.map(err => err.msg || JSON.stringify(err)).join(', ')
      const error = new Error(messages)
      error.response = data
      throw error
    }

    // detail이 문자열인 경우 (일반 에러)
    const error = new Error(data.detail || '요청 처리 중 오류가 발생했습니다.')
    error.response = data
    throw error
  }

  if (response.status === 204) return null
  return response.json()
}
