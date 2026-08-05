import asyncio

import pyupbit


async def get_current_price(ticker: str) -> float:
    """동기 pyupbit 현재가 조회를 이벤트 루프 밖에서 실행합니다."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: pyupbit.get_current_price(ticker))
    return float(result or 0)


async def get_market_tickers(markets: list[str]) -> list[dict]:
    """여러 종목의 현재가와 등락률을 한 번에 조회합니다.

    개별 종목마다 get_current_price를 반복 호출하면 업비트 API를 여러 번
    두드리게 되므로, 배치 조회가 가능한 pyupbit의 verbose 모드를 씁니다.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: pyupbit.get_current_price(markets, verbose=True)
    )
    return result or []
    result = await loop.run_in_executor(
        None, lambda: pyupbit.get_current_price(markets, verbose=True)
    )
    return result or []
