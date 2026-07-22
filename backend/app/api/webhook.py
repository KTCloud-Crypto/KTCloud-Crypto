import json as _json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.api_key import ApiKey
from app.models.position import Position
from app.models.trade import Trade
from app.models.user import User
from app.services import upbit_service as upbit
from app.services.crypto import decrypt
from app.services.telegram import send_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhook"])


def _parse_action_ticker(raw: bytes) -> tuple[str, str]:
    try:
        body = _json.loads(raw) if raw else {}
    except Exception:
        body = {}

    action = body.get("action", "").lower()
    raw_ticker = body.get("ticker") or body.get("symbol") or ""

    if not action or not raw_ticker:
        text = raw.decode("utf-8", errors="replace")
        m = re.search(r"(?:order|오더)\s+(buy|sell).*?(?:on|필드 온)\s+(\w+)", text, re.IGNORECASE)
        if m:
            action = m.group(1).lower()
            raw_ticker = m.group(2)

    raw_ticker = raw_ticker.upper()
    for suffix in ("USDT", "USD", "BUSD", "PERP", "KRW"):
        if raw_ticker.endswith(suffix):
            raw_ticker = raw_ticker[: -len(suffix)]
            break
    ticker = f"KRW-{raw_ticker}" if raw_ticker and not raw_ticker.startswith("KRW-") else raw_ticker
    return action, ticker


def _get_position(db: Session, user_id: int, ticker: str) -> Position | None:
    return db.query(Position).filter(Position.user_id == user_id, Position.ticker == ticker).first()


def _set_position(db: Session, user_id: int, ticker: str, status: str | None) -> None:
    position = _get_position(db, user_id, ticker)
    if position is None:
        position = Position(user_id=user_id, ticker=ticker, status=status)
        db.add(position)
    else:
        position.status = status
    db.commit()


@router.post("/webhook/{token}")
async def webhook(token: str, request: Request, db: Session = Depends(get_db)):
    """TradingView 웹훅 신호를 수신하여 매수/매도를 실행합니다."""
    user = db.query(User).filter(User.webhook_token == token).first()
    if user is None:
        raise HTTPException(status_code=404, detail="유효하지 않은 웹훅 URL입니다.")

    raw = await request.body()
    logger.info(f"[RAW] user_id={user.id} body={raw.decode('utf-8', errors='replace')}")

    action, ticker = _parse_action_ticker(raw)
    logger.info(f"[PARSED] user_id={user.id} action={action} ticker={ticker}")

    if not action or not ticker:
        return {"status": "ignored", "reason": "action/ticker 누락"}

    if not user.bot_enabled:
        return {"status": "ignored", "reason": "봇 비활성화 상태"}

    api_key = db.query(ApiKey).filter(ApiKey.user_id == user.id).first()
    if api_key is None:
        return {"status": "ignored", "reason": "거래소 API Key 미등록"}

    access_key = decrypt(api_key.encrypted_access_key)
    secret_key = decrypt(api_key.encrypted_secret_key)

    if action == "buy":
        position = _get_position(db, user.id, ticker)
        if position and position.status == "long":
            return {"status": "ignored", "reason": f"{ticker} 이미 보유 중"}

        result = await upbit.buy_market_order(ticker, access_key, secret_key)
        price = await upbit.get_current_price(ticker)
        if result and not result.get("error"):
            _set_position(db, user.id, ticker, "long")
            db.add(Trade(user_id=user.id, ticker=ticker, action="buy", price=price, volume=result.get("volume"), status="success", raw_response=result))
            db.commit()
            send_message(user.telegram_chat_id, f"✅ 매수 완료\n{ticker}\n현재가: {price:,.2f}원")
        else:
            db.add(Trade(user_id=user.id, ticker=ticker, action="buy", price=price, volume=None, status="failed", raw_response=None))
            db.commit()
            send_message(user.telegram_chat_id, f"❌ 매수 실패: {ticker}")
            return {
                "status": "failed",
                "action": action,
                "ticker": ticker,
                "reason": "Upbit 주문 실패",
            }

    elif action == "sell":
        position = _get_position(db, user.id, ticker)
        if not position or position.status != "long":
            return {"status": "ignored", "reason": f"{ticker} 보유 포지션 없음"}

        result = await upbit.sell_market_order(ticker, access_key, secret_key)
        price = await upbit.get_current_price(ticker)
        if result and not result.get("error"):
            _set_position(db, user.id, ticker, None)
            db.add(Trade(user_id=user.id, ticker=ticker, action="sell", price=price, volume=result.get("volume"), status="success", raw_response=result))
            db.commit()
            send_message(user.telegram_chat_id, f"✅ 매도 완료\n{ticker}\n현재가: {price:,.2f}원")
        else:
            db.add(Trade(user_id=user.id, ticker=ticker, action="sell", price=price, volume=None, status="failed", raw_response=None))
            db.commit()
            send_message(user.telegram_chat_id, f"❌ 매도 실패: {ticker}")
            return {
                "status": "failed",
                "action": action,
                "ticker": ticker,
                "reason": "Upbit 주문 실패",
            }

    else:
        return {"status": "ignored", "reason": f"알 수 없는 action: {action}"}

    return {"status": "ok", "action": action, "ticker": ticker}
