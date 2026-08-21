export function coinIconForCurrency(currency) {
  if (!currency) return null
  return `/coins/${currency.toLowerCase()}.svg`
}

export function coinIconForMarket(market) {
  return coinIconForCurrency(market?.split('-').at(-1))
}
