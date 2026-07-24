import asyncio
import pyupbit


async def get_current_price(ticker: str) -> float:
    """동기 pyupbit 현재가 조회를 이벤트 루프 밖에서 실행합니다."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: pyupbit.get_current_price(ticker))
    return float(result or 0)
