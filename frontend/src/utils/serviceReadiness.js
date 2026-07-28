/**
 * 상단바에 표시할 서비스 준비 상태를 만듭니다.
 *
 * 별도 API를 부르지 않고 이미 조회한 user 정보만으로 계산하므로,
 * 어느 페이지에서 호출하든 추가 요청이 발생하지 않습니다.
 *
 * Upbit 항목은 "키가 등록되어 있는지"만 확인합니다. 키가 만료됐거나 허용 IP가
 * 달라 실제 조회가 실패하는 경우까지는 구분하지 못하므로, 정확한 연결 상태는
 * 실전투자 화면에서 확인해야 합니다.
 */
export function serviceReadiness(user) {
  return [
    {
      label: 'Upbit API',
      ready: Boolean(user?.has_api_key),
      detail: user?.has_api_key ? 'API 키 등록됨' : 'API 키 등록 필요',
    },
    {
      label: 'Telegram',
      ready: Boolean(user?.telegram_chat_id),
      detail: user?.telegram_chat_id ? '체결 알림 연결됨' : '알림 연결 필요',
    },
    {
      label: '자동매매',
      ready: Boolean(user?.bot_enabled),
      detail: user?.bot_enabled ? '신호 수신 활성화' : '현재 중지 상태',
    },
  ]
}
 