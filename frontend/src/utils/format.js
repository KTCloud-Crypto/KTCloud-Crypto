/** API가 반환하는 timezone 없는 UTC 시각을 브라우저의 한국 시각으로 표시합니다. */
export function formatUtcDateTime(value) {
  if (!value) return '-'
  const utcValue = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`
  return new Date(utcValue).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
}

export function formatNumber(value, maximumFractionDigits = 0) {
  if (value == null) return '-'
  return value.toLocaleString(undefined, { maximumFractionDigits })
}
