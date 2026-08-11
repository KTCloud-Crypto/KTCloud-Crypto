/**
 * 초보자를 위한 추천 세팅 3개입니다. 종목만 고르면 전략·분봉·손절·익절이
 * 모두 이 값으로 자동 세팅되고, 사용자는 투자 비율만 정하면 됩니다.
 *
 * 신규 전략(RSI-MACD 복합 확인, 볼린저 밴드 수축 돌파, 변동성 돌파)만 대상으로 하며,
 * 기존 5개 전략은 이용 가이드의 "전략 알아보기"에서 별도로 설명합니다.
 */
export const RECOMMENDED_PRESETS = [
  {
    id: 'rsi-macd-confirm',
    strategyCode: 'rsi_macd_confirm_v1',
    label: 'RSI-MACD 복합 확인',
    description: '두 지표가 동시에 같은 신호를 낼 때만 매매해서, 가짜 신호를 줄이는 전략이에요.',
    detail: (
      <>
        MACD가 실제로 골든크로스(또는 데드크로스)를 낸 순간에, RSI도 매수라면 30~50 구간, 매도라면 70 이상 구간에 있을 때만{' '}
        <strong>최종 신호로 인정</strong>합니다. 지표 하나만 보면 자주 나오는 가짜 신호(휩소)를{' '}
        <strong>두 지표가 서로 검증하게 만든 방식</strong>이에요. 30분봉을 써서 짧은 분봉의 잔노이즈를 줄였고,{' '}
        <strong>손절 -2.5% · 익절 +4%</strong>로 한 번 이익 날 때 손실보다 조금 더 크게 가져가도록 설계했어요.
      </>
    ),
    timeframe: 30,
    stopLoss: 2.5,
    takeProfit: 4,
    defaultRatio: 20,
  },
  {
    id: 'bollinger-squeeze',
    strategyCode: 'bollinger_squeeze_breakout_v1',
    label: '볼린저 밴드 수축 돌파',
    description: '가격이 잠잠하다가 갑자기 크게 움직이기 시작하는 순간을 포착해요.',
    detail: (
      <>
        최근 밴드 폭이 평소보다 좁아진 구간을 "에너지가 응축된 상태"로 보고,{' '}
        <strong>가격이 밴드 상단이나 하단을 뚫고 나가는 순간</strong>을 신호로 삼습니다. 15분봉을 써서 수축 이후 돌파가 나오는 타이밍을 촘촘하게 포착하고, 돌파형 전략 특성상 빠른 대응이 중요해{' '}
        <strong>손절 -2% · 익절 +3%</strong>로 짧고 타이트하게 끊도록 설계했어요.
      </>
    ),
    timeframe: 15,
    stopLoss: 2,
    takeProfit: 3,
    defaultRatio: 20,
  },
  {
    id: 'volatility-breakout',
    strategyCode: 'volatility_breakout_v1',
    label: '변동성 돌파',
    description: '전날 하루 동안의 가격 변동폭을 기준으로, 오늘 그만큼 움직이면 올라타는 전략이에요.',
    detail: (
      <>
        "어제 이만큼 움직였으니, 오늘도 그 절반만큼만 더 오르면 오늘도 크게 움직이는 날일 확률이 높다"는 생각에서 나온 전략이에요.{' '}
        <strong>그 기준선을 넘으면 매수</strong>하고, 하루가 지나면 자동으로 정리한 뒤 다음 날 기준을 다시 잡습니다. 하루 단위로 크게 보는 전략이라 60분마다 확인하고요. 이런 돌파 전략은 맞을 때보다 틀릴 때가 더 많을 수 있어서, 대신{' '}
        <strong>틀렸을 때는 조금만 잃고(-3%) 맞았을 때는 크게 버는(+9%)</strong> 방식으로 균형을 맞췄어요.
      </>
    ),
    timeframe: 60,
    stopLoss: 3,
    takeProfit: 9,
    defaultRatio: 20,
  },
]