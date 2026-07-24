import { useEffect, useRef } from 'react'

/** 콜백의 최신 버전을 유지하면서 컴포넌트 생명주기에 맞춰 반복 조회합니다. */
export function usePolling(callback, intervalMs, refreshKey = '') {
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    callbackRef.current()
    const timer = window.setInterval(() => callbackRef.current(), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs, refreshKey])
}
