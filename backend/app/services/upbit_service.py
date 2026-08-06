import asyncio
import time

import pyupbit

RETRY_COUNT = 2
RETRY_DELAY_SECONDS = 0.5


async def get_current_price(ticker: str) -> float:
    """동기 pyupbit 현재가 조회를 이벤트 루프 밖에서 실행합니다.

    일시적인 네트워크 지연에 대비해 짧게 재시도합니다. 시세는 초 단위로도
    바뀔 수 있어 간격을 0.5초로 타이트하게 잡아 지연을 최소화합니다.
    """
    loop = asyncio.get_event_loop()
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            result = await loop.run_in_executor(None, lambda: pyupbit.get_current_price(ticker))
            if result is not None:
                return float(result)
            last_error = ValueError("현재가 조회 결과가 비어 있습니다.")
        except Exception as error:
            last_error = error
        if attempt < RETRY_COUNT:
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise ValueError(f"Upbit 현재가 조회에 실패했습니다: {ticker}") from last_error


async def get_market_tickers(markets: list[str]) -> list[dict]:
    """여러 종목의 현재가와 등락률을 한 번에 조회합니다.

    개별 종목마다 get_current_price를 반복 호출하면 업비트 API를 여러 번
    두드리게 되므로, 배치 조회가 가능한 pyupbit의 verbose 모드를 씁니다.
    일시적인 네트워크 지연에 대비해 짧게 재시도합니다.
    """
    loop = asyncio.get_event_loop()
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            result = await loop.run_in_executor(
                None, lambda: pyupbit.get_current_price(markets, verbose=True)
            )
            return result or []
        except Exception as error:
            last_error = error
        if attempt < RETRY_COUNT:
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise ValueError("Upbit 시세 일괄 조회에 실패했습니다.") from last_error