import { useEffect, useRef } from 'react'

/** 콜백의 최신 버전을 유지하면서 컴포넌트 생명주기에 맞춰 반복 조회합니다. */
export function usePolling(callback, intervalMs, refreshKey = '') {
  const callbackRef = useRef(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    let cancelled = false
    let timer = null

    const run = async () => {
      try {
        await callbackRef.current()
      } finally {
        if (!cancelled) timer = window.setTimeout(run, intervalMs)
      }
    }

    run()
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [intervalMs, refreshKey])
}
