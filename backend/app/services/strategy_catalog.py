"""서비스에서 제공하는 기본 전략 카탈로그."""

from sqlalchemy.orm import Session

from app.models.strategy import Strategy, SupportedMarket

MARKET_CATALOG = [
    ("KRW-BTC", "비트코인"),
    ("KRW-ETH", "이더리움"),
    ("KRW-XRP", "리플"),
    ("KRW-SOL", "솔라나"),
    ("KRW-DOGE", "도지코인"),
    ("KRW-TRX", "트론"),
]


STRATEGY_CATALOG = [
    {
        "code": "manual_hold_v1",
        "name": "미배정 자산",
        "description": "Upbit에 보유 중이지만 자동매매 전략에 배정하지 않은 자산입니다. 자동매매 신호와 주문이 실행되지 않습니다.",
        "timeframe_minutes": 10,
        "parameters": {},
        "default_invest_ratio": 0.0,
        "enabled": False,  # UI에 표시하지 않음
    },
    {
        "code": "sma_cross_v1",
        "name": "이동평균 교차 전략",
        "description": "5기간 SMA가 20기간 SMA를 상향 돌파하면 매수하고 하향 돌파하면 매도합니다.",
        "timeframe_minutes": 10,
        "parameters": {"short_window": 5, "long_window": 20},
        "default_invest_ratio": 0.0,
        "enabled": True,
    },
    {
        "code": "rsi_reversal_v1",
        "name": "RSI 과매수·과매도 반전",
        "description": "RSI(14)가 30 아래에서 복귀하면 매수하고 70 위에서 하락 복귀하면 매도합니다.",
        "timeframe_minutes": 10,
        "parameters": {"period": 14, "oversold": 30, "overbought": 70},
        "default_invest_ratio": 0.0,
        "enabled": True,
    },
    {
        "code": "macd_cross_v1",
        "name": "MACD 크로스",
        "description": "MACD(12, 26)가 시그널선(9)을 상향 돌파하면 매수하고 하향 돌파하면 매도합니다.",
        "timeframe_minutes": 10,
        "parameters": {"fast": 12, "slow": 26, "signal": 9},
        "default_invest_ratio": 0.0,
        "enabled": True,
    },
    {
        "code": "bollinger_reentry_v1",
        "name": "볼린저 밴드 회귀",
        "description": "종가가 20기간 ±2σ 밴드 밖으로 이탈했다가 밴드 안으로 복귀할 때 매매합니다.",
        "timeframe_minutes": 10,
        "parameters": {"window": 20, "deviation": 2},
        "default_invest_ratio": 0.0,
        "enabled": True,
    },
    {
        "code": "donchian_breakout_v1",
        "name": "돈치안 채널 돌파",
        "description": "종가가 이전 20개 캔들의 최고가를 돌파하면 매수하고 최저가를 이탈하면 매도합니다.",
        "timeframe_minutes": 10,
        "parameters": {"window": 20},
        "default_invest_ratio": 0.0,
        "enabled": True,
    },
]


def seed_strategy_catalog(db: Session) -> None:
    """코드로 관리되는 전략 정의를 DB 카탈로그와 동기화합니다."""
    markets = {item.code: item for item in db.query(SupportedMarket).all()}
    active_market_codes = {code for code, _ in MARKET_CATALOG}
    for market in markets.values():
        if market.code not in active_market_codes:
            market.enabled = False

    for index, (code, display_name) in enumerate(MARKET_CATALOG, start=1):
        market = markets.get(code)
        if market is None:
            db.add(SupportedMarket(
                code=code,
                display_name=display_name,
                enabled=True,
                sort_order=index,
            ))
        else:
            market.display_name = display_name
            market.enabled = True
            market.sort_order = index

    existing = {item.code: item for item in db.query(Strategy).all()}
    for definition in STRATEGY_CATALOG:
        strategy = existing.get(definition["code"])
        if strategy is None:
            db.add(Strategy(**definition))
            continue
        for field, value in definition.items():
            setattr(strategy, field, value)
    db.commit()
