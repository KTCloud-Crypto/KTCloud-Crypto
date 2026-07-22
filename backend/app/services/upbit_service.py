import asyncio
import logging
from decimal import Decimal, ROUND_DOWN

import pyupbit

logger = logging.getLogger(__name__)

BUY_RATIO = 0.9995  # 수수료 고려 99.95%
VOLUME_PRECISION = Decimal("0.00000001")


def _client(access_key: str, secret_key: str) -> pyupbit.Upbit:
    return pyupbit.Upbit(access_key, secret_key)


def calculate_buy_volume(krw: float, ask_price: float) -> float:
    """잔고를 초과하지 않도록 매수 수량을 소수점 8자리에서 내림 처리합니다."""
    volume = (
        Decimal(str(krw))
        * Decimal(str(BUY_RATIO))
        / Decimal(str(ask_price))
    )
    return float(volume.quantize(VOLUME_PRECISION, rounding=ROUND_DOWN))


async def get_balance_krw(access_key: str, secret_key: str) -> float:
    loop = asyncio.get_event_loop()
    upbit = _client(access_key, secret_key)
    result = await loop.run_in_executor(None, lambda: upbit.get_balance("KRW"))
    return float(result or 0)


async def get_balance_coin(ticker: str, access_key: str, secret_key: str) -> float:
    loop = asyncio.get_event_loop()
    upbit = _client(access_key, secret_key)
    coin = ticker.replace("KRW-", "")
    result = await loop.run_in_executor(None, lambda: upbit.get_balance(coin))
    return float(result or 0)


async def get_current_price(ticker: str) -> float:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: pyupbit.get_current_price(ticker))
    return float(result or 0)


async def _get_orderbook(ticker: str) -> dict:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: pyupbit.get_orderbook(ticker))
    if isinstance(result, list):
        return result[0] if result else {}
    return result or {}


async def buy_market_order(ticker: str, access_key: str, secret_key: str) -> dict | None:
    """매도1호가로 지정가 매수 주문을 넣습니다 (시장가 슬리피지 방지)."""
    loop = asyncio.get_event_loop()
    upbit = _client(access_key, secret_key)

    orderbook = await _get_orderbook(ticker)
    ask_price = orderbook["orderbook_units"][0]["ask_price"]

    krw = await get_balance_krw(access_key, secret_key)
    volume = calculate_buy_volume(krw, ask_price)

    logger.info(f"[BUY] ticker={ticker} krw={krw} ask_price={ask_price} volume={volume}")
    try:
        result = await loop.run_in_executor(
            None, lambda: upbit.buy_limit_order(ticker, ask_price, volume)
        )
    except Exception as e:
        logger.error(f"[BUY] exception={e}")
        return None
    logger.info(f"[BUY] result={result}")
    return result


async def sell_market_order(ticker: str, access_key: str, secret_key: str) -> dict | None:
    """매수1호가로 지정가 매도 주문을 넣습니다 (시장가 슬리피지 방지)."""
    loop = asyncio.get_event_loop()
    upbit = _client(access_key, secret_key)

    orderbook = await _get_orderbook(ticker)
    bid_price = orderbook["orderbook_units"][0]["bid_price"]

    qty = await get_balance_coin(ticker, access_key, secret_key)

    logger.info(f"[SELL] ticker={ticker} bid_price={bid_price} qty={qty}")
    try:
        result = await loop.run_in_executor(
            None, lambda: upbit.sell_limit_order(ticker, bid_price, qty)
        )
    except Exception as e:
        logger.error(f"[SELL] exception={e}")
        return None
    logger.info(f"[SELL] result={result}")
    return result
