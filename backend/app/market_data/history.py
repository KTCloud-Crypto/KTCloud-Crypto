from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.market_data.candles import Candle


async def fetch_completed_minute_candles(
    market: str,
    interval_minutes: int,
    count: int,
) -> list[Candle]:
    """전략 계산기 초기화를 위해 마감된 Upbit 분봉을 과거순으로 조회합니다."""
    async with httpx.AsyncClient(base_url=settings.upbit_api_base_url, timeout=10.0) as client:
        response = await client.get(
            f"/v1/candles/minutes/{interval_minutes}",
            params={"market": market, "count": min(count + 1, 200)},
        )
        response.raise_for_status()
        rows = response.json()

    interval_ms = interval_minutes * 60 * 1000
    current_bucket_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    current_bucket_ms -= current_bucket_ms % interval_ms
    candles: list[Candle] = []

    for row in rows:
        open_time = datetime.fromisoformat(row["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
        open_time_ms = int(open_time.timestamp() * 1000)
        if open_time_ms >= current_bucket_ms:
            continue
        candles.append(
            Candle(
                market=market,
                interval_minutes=interval_minutes,
                open_time_ms=open_time_ms,
                open=float(row["opening_price"]),
                high=float(row["high_price"]),
                low=float(row["low_price"]),
                close=float(row["trade_price"]),
                volume=float(row["candle_acc_trade_volume"]),
            )
        )

    candles.sort(key=lambda candle: candle.open_time_ms)
    return candles[-count:]
