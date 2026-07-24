const DISPLAY = {
  sma_cross_v1: {
    parameters: ({ short_window: short, long_window: long }) => `SMA ${short}/${long}`,
    metrics: [
      ['short_sma', '단기 SMA'],
      ['long_sma', '장기 SMA'],
    ],
  },
  rsi_reversal_v1: {
    parameters: ({ period, oversold, overbought }) => `RSI ${period} · ${oversold}/${overbought}`,
    metrics: [['rsi', 'RSI']],
  },
  macd_cross_v1: {
    parameters: ({ fast, slow, signal }) => `MACD ${fast}/${slow}/${signal}`,
    metrics: [
      ['macd', 'MACD'],
      ['signal', '시그널'],
      ['histogram', '히스토그램'],
    ],
  },
  bollinger_reentry_v1: {
    parameters: ({ window, deviation }) => `볼린저 ${window} · ${deviation}σ`,
    metrics: [
      ['middle', '중심선'],
      ['upper', '상단 밴드'],
      ['lower', '하단 밴드'],
    ],
  },
  donchian_breakout_v1: {
    parameters: ({ window }) => `돈치안 ${window}`,
    metrics: [
      ['upper', '상단 채널'],
      ['lower', '하단 채널'],
    ],
  },
}

export function parameterSummary(strategy) {
  return DISPLAY[strategy.code]?.parameters(strategy.parameters) ?? strategy.code
}

export function metricEntries(code, metrics = {}) {
  const definitions = DISPLAY[code]?.metrics ?? Object.keys(metrics).map((key) => [key, key])
  return definitions
    .filter(([key]) => metrics[key] != null)
    .map(([key, label]) => ({ key, label, value: metrics[key] }))
}
