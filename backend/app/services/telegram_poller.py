from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.api_key import ApiKey
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.user import User
from app.services.exchange_credentials import resolve_exchange_credentials
from app.services.position_reconciliation import (
    recorded_strategy_positions,
    recorded_strategy_volumes,
    reconciliation_status,
)
from app.services.position_sync import PositionSyncError, actual_coin_totals, apply_position_sync
from app.services.signal_dispatcher import dispatch_signal
from app.services.security import SimpleRateLimiter
from app.services.strategy_positions import load_strategy_position
from app.services.upbit import get_accounts
from app.services.upbit_service import get_current_price

logger = logging.getLogger(__name__)
COMMAND_TIMEOUT = timedelta(minutes=2)
find_id_limiter = SimpleRateLimiter(window_seconds=300, max_requests=5)
STRATEGY_ALIASES = {
    "sma_cross_v1": "sma",
    "rsi_reversal_v1": "rsi",
    "macd_cross_v1": "macd",
    "bollinger_reentry_v1": "bollinger",
    "donchian_breakout_v1": "donchian",
}


@dataclass(frozen=True, slots=True)
class PendingCommand:
    action: str
    expires_at: datetime
    strategy_ids: tuple[int, ...] = ()


def _linked_user(db, chat_id: str) -> User | None:
    return db.query(User).filter(User.telegram_chat_id == chat_id).first()


def _find_id_text(chat_id: str) -> str:
    """Telegram chat ID에 연결된 로그인 아이디를 안내합니다."""
    if not find_id_limiter.allow(f"telegram-find-id:{chat_id}"):
        return "⚠️ 요청이 너무 많습니다. 5분 후 다시 시도해 주세요."
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 이 텔레그램에는 연결된 SignalTrade 계정이 없습니다."
        return f"👤 SignalTrade 계정 안내\n\n아이디: {user.username}\n\n로그인 화면에서 이 아이디를 사용해 주세요."
    finally:
        db.close()


def _alias(strategy: Strategy) -> str:
    return STRATEGY_ALIASES.get(strategy.code, strategy.code.removesuffix("_v1"))


def _strategy_command(
    subscription: UserStrategy,
    strategy: Strategy,
    market: SupportedMarket,
) -> str:
    prefix = "paper" if subscription.mode == "simulated" else "live"
    symbol = market.code.split("-", maxsplit=1)[-1].lower()
    return f"{prefix}_{symbol}_{_alias(strategy)}"


def _strategy_rows(db, user: User):
    return (
        db.query(UserStrategy, Strategy, SupportedMarket)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            UserStrategy.user_id == user.id,
            UserStrategy.enabled.is_(True),
            Strategy.enabled.is_(True),
        )
        .order_by(SupportedMarket.sort_order, Strategy.id)
        .all()
    )


def _help_text() -> str:
    return (
        "🤖 [SignalTrade 명령어]\n\n"
        "/status - 자동매매 상태\n"
        "/pause - 전략 신규 매수 일시정지\n"
        "/resume - 일시정지 전략 재개\n"
        "/balance - Upbit 잔고 조회\n"
        "/positions - 전략별 포지션 조회\n"
        "/findid - 연결된 SignalTrade 아이디 찾기\n"
        "/close - 전략 포지션 전량 매도\n"
        "/sync - 실제 잔고와 전략 기록 비교\n"
        "/cancel - 진행 중인 명령 취소\n"
        "/help - 명령어 다시 보기"
    )


def _strategy_menu(chat_id: str, action: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        paused = action == "resume"
        rows = [
            (subscription, strategy, market)
            for subscription, strategy, market in _strategy_rows(db, user)
            if subscription.paused is paused
        ]
        label = "재개" if paused else "일시정지"
        if not rows:
            return f"ℹ️ 현재 {label}할 전략이 없습니다."
        lines = [
            f"{'▶️' if paused else '⏸️'} [자동매매 {label}]",
            "",
            f"현재 {label} 가능한 전략입니다.",
            "",
        ]
        for subscription, strategy, market in rows:
            mode = "모의" if subscription.mode == "simulated" else "실전"
            lines.append(
                f"/{_strategy_command(subscription, strategy, market)} - [{mode}] {market.code} · {strategy.name}"
            )
        lines.extend(["", f"/all - 모든 전략 {label}", "/cancel - 취소"])
        return "\n".join(lines)
    finally:
        db.close()


def _set_pause(chat_id: str, action: str, selection: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        rows = _strategy_rows(db, user)
        target_paused = action == "pause"
        candidates = [
            (subscription, strategy, market)
            for subscription, strategy, market in rows
            if subscription.paused is not target_paused
        ]
        if selection != "all":
            candidates = [
                item
                for item in candidates
                if _strategy_command(item[0], item[1], item[2]) == selection
            ]
        if not candidates:
            return "⚠️ 선택할 수 없는 전략입니다. 표시된 명령을 입력하거나 /cancel로 취소해 주세요."
        for subscription, _, _ in candidates:
            subscription.paused = target_paused
        db.commit()
        names = ", ".join(
            f"[{'모의' if subscription.mode == 'simulated' else '실전'}] {market.code} · {strategy.name}"
            for subscription, strategy, market in candidates
        )
        if target_paused:
            return (
                f"⏸️ 신규 매수를 일시정지했습니다.\n\n📌 전략: {names}\n"
                "🛡️ 기존 포지션의 매도 신호와 손절·익절은 계속 처리됩니다.\n"
                "다시 시작하려면 /resume을 입력해 주세요."
            )
        return f"▶️ 자동매매를 재개했습니다.\n\n📌 전략: {names}"
    finally:
        db.close()


def _status_text(chat_id: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        rows = _strategy_rows(db, user)
        lines = ["📊 [자동매매 상태]"]
        if not rows:
            lines.append("\n📭 실행 중인 전략이 없습니다.")
        else:
            for mode, mode_label in (("simulated", "🧪 모의투자"), ("live", "💵 실전투자")):
                mode_rows = [item for item in rows if item[0].mode == mode]
                lines.append(f"\n{mode_label}")
                if not mode_rows:
                    lines.append("📭 활성 전략 없음")
                    continue
                for subscription, strategy, market in mode_rows:
                    state = "⏸️ 신규 매수 중지" if subscription.paused else "🟢 실행 중"
                    lines.append(
                        f"{state} · {market.code} · {strategy.name}\n"
                        f"   {subscription.timeframe_minutes}분봉 · 투자 비율 {subscription.invest_ratio * 100:.0f}%"
                    )
        return "\n".join(lines)
    finally:
        db.close()


def _balance_text(chat_id: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        accounts = _accounts_for_user(db, user.id)
        lines = ["💰 [Upbit 보유 잔고]"]
        for account in accounts:
            currency = str(account.get("currency") or "")
            balance = float(account.get("balance") or 0)
            locked = float(account.get("locked") or 0)
            if balance <= 0 and locked <= 0:
                continue
            if currency == "KRW":
                locked_text = f" (주문 중 {locked:,.0f}원)" if locked > 0 else ""
                lines.append(f"\n🇰🇷 KRW: {balance:,.0f}원{locked_text}")
            else:
                balance_text = f"{balance:.8f}".rstrip("0").rstrip(".")
                locked_text = ""
                if locked > 0:
                    locked_text = f" (주문 중 {f'{locked:.8f}'.rstrip('0').rstrip('.')})"
                lines.append(f"\n🪙 {currency}: {balance_text}{locked_text}")
        return "\n".join(lines)
    finally:
        db.close()


def _positions_text(chat_id: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        lines = ["📦 [전략별 포지션]"]
        found = False
        for subscription, strategy, market in _strategy_rows(db, user):
            position = load_strategy_position(db, subscription.id, subscription.mode)
            if position.volume <= 0:
                continue
            found = True
            lines.append(
                f"\n📈 {strategy.name}\n"
                f"   종목: {market.code}\n"
                f"   수량: {position.volume:.8f}\n"
                f"   평균 매수가: {position.average_buy_price or 0:,.0f}원"
            )
        if not found:
            lines.append("\n📭 현재 보유한 전략 포지션이 없습니다.")
        return "\n".join(lines)
    finally:
        db.close()


def _position_for_subscription(db, subscription: UserStrategy):
    return load_strategy_position(db, subscription.id, subscription.mode)


def _close_candidates(db, user: User):
    candidates = []
    for subscription, strategy, market in _strategy_rows(db, user):
        position = _position_for_subscription(db, subscription)
        if position.volume > 0:
            candidates.append((subscription, strategy, market, position))
    return candidates


def _close_menu(chat_id: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        candidates = _close_candidates(db, user)
        if not candidates:
            return "📭 전량 매도할 전략 포지션이 없습니다."
        lines = [
            "🚨 [포지션 전량 매도]",
            "",
            "매도할 포지션을 선택해 주세요.",
            "",
        ]
        for subscription, strategy, market, position in candidates:
            mode = "모의" if subscription.mode == "simulated" else "실전"
            lines.append(
                f"/{_strategy_command(subscription, strategy, market)} - [{mode}] "
                f"{market.code} · {strategy.name} · {position.volume:.8f}"
            )
        lines.extend(["", "/all - 모든 포지션", "/cancel - 취소"])
        return "\n".join(lines)
    finally:
        db.close()


def _prepare_close(chat_id: str, selection: str) -> tuple[str, tuple[int, ...]]:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요.", ()
        candidates = _close_candidates(db, user)
        if selection != "all":
            candidates = [
                item
                for item in candidates
                if _strategy_command(item[0], item[1], item[2]) == selection
            ]
        if not candidates:
            return "⚠️ 선택할 수 없는 포지션입니다. 표시된 명령을 입력하거나 /cancel로 취소해 주세요.", ()

        lines = ["⚠️ [전량 매도 최종 확인]", ""]
        for subscription, strategy, market, position in candidates:
            mode = "모의" if subscription.mode == "simulated" else "실전"
            lines.append(f"• [{mode}] {market.code} · {strategy.name}: {position.volume:.8f}")
        lines.extend([
            "",
            "선택한 포지션을 시장가로 전량 매도합니다.",
            "/confirm - 매도 실행",
            "/cancel - 취소",
        ])
        return "\n".join(lines), tuple(item[0].id for item in candidates)
    finally:
        db.close()


async def _execute_close(chat_id: str, strategy_ids: tuple[int, ...]) -> str:
    """확인된 전략을 다시 조회하고 기존 수동 매도 경로로 모드별 청산합니다."""
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        rows = [
            (subscription, strategy, market)
            for subscription, strategy, market in _strategy_rows(db, user)
            if subscription.id in strategy_ids
            and _position_for_subscription(db, subscription).volume > 0
        ]
        user_id = user.id
    finally:
        db.close()

    if not rows:
        return "📭 매도할 포지션이 없거나 이미 청산되었습니다."

    requested = 0
    failures = []
    for subscription, strategy, market in rows:
        try:
            price = await get_current_price(market.code)
            if price <= 0:
                raise ValueError("현재가를 조회하지 못했습니다.")
            db = SessionLocal()
            try:
                signal = StrategySignal(
                    strategy_id=strategy.id,
                    market=market.code,
                    timeframe_minutes=subscription.timeframe_minutes,
                    action="sell",
                    source="manual",
                    candle_open_time=datetime.utcnow(),
                    close_price=price,
                    metrics={"telegram_manual_price": price},
                )
                db.add(signal)
                db.commit()
                db.refresh(signal)
                signal_id = signal.id
            finally:
                db.close()
            requested += await dispatch_signal(
                signal_id,
                user_id=user_id,
                mode=subscription.mode,
            )
        except Exception as error:
            logger.warning(
                "Telegram close failed: strategy_id=%s error=%s",
                strategy.id,
                type(error).__name__,
            )
            failures.append(strategy.name)

    if failures:
        return (
            f"⚠️ 전량 매도 요청 {requested}건을 전달했습니다.\n"
            f"❌ 처리하지 못한 전략: {', '.join(failures)}\n"
            "체결 결과는 별도 Telegram 알림에서 확인해 주세요."
        )
    return (
        f"✅ 전량 매도 요청 {requested}건을 전달했습니다.\n"
        "체결 결과는 별도 Telegram 알림에서 확인해 주세요."
    )


def _link_chat(code: str, chat_id: str) -> bool:
    """유효한 일회용 코드의 사용자에게 Telegram chat ID를 연결합니다."""
    normalized_code = code.strip().upper()
    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(
                User.telegram_link_code == normalized_code,
                User.telegram_link_expires_at >= datetime.utcnow(),
            )
            .first()
        )
        if user is None:
            return False

        user.telegram_chat_id = chat_id
        user.telegram_link_code = None
        user.telegram_link_expires_at = None
        db.commit()
        return True
    finally:
        db.close()


def _accounts_for_user(db, user_id: int) -> list[dict]:
    """연결된 사용자의 암호화된 키로 현재 Upbit 잔고를 조회합니다."""
    api_key = db.query(ApiKey).filter(ApiKey.user_id == user_id).first()
    if api_key is None:
        raise PositionSyncError("등록된 Upbit API Key가 없습니다.")
    access_key, secret_key = resolve_exchange_credentials(api_key)
    return get_accounts(access_key, secret_key, settings.upbit_api_base_url)


def _sync_menu(chat_id: str) -> tuple[str, dict | None]:
    """현재 불일치와 적용 가능한 전략 버튼을 Telegram 메시지 형태로 만듭니다."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요.", None

        accounts = _accounts_for_user(db, user.id)
        actual = actual_coin_totals(accounts)
        recorded = recorded_strategy_volumes(db, user.id)
        positions = recorded_strategy_positions(db, user.id)
        lines = ["🔄 [실전 포지션 동기화]"]
        buttons = []
        shortfall_count = 0
        unallocated_count = 0
        for currency in sorted(set(actual) | set(recorded)):
            actual_total = actual.get(currency, 0.0)
            strategy_total = recorded.get(currency, 0.0)
            item_status, _ = reconciliation_status(actual_total, strategy_total)
            if item_status == "matched":
                continue

            difference = actual_total - strategy_total
            if item_status == "external_balance":
                unallocated_count += 1
                lines.extend([
                    "",
                    f"🪙 {currency}: 외부/미배정 {difference:.8f}",
                    "ℹ️ 계좌 자산으로만 표시되며 자동매매에는 포함되지 않습니다.",
                ])
                continue

            shortfall_count += 1
            lines.extend([
                "",
                f"🪙 {currency}: 실제 {actual_total:.8f} / 전략 {strategy_total:.8f}",
                f"⚖️ 차이: {difference:+.8f}",
            ])
            candidates = [
                item for item in positions
                if item.market.endswith(f"-{currency}")
                and item.volume > 0
            ]
            for item in candidates:
                buttons.append([{
                    "text": f"{item.strategy.name}에서 차감",
                    "callback_data": f"psync|deduct|{currency}|{item.subscription.id}",
                }])
            if not candidates:
                lines.append("⚠️ 적용 가능한 실전 전략이 없습니다. 웹에서 전략을 먼저 설정해 주세요.")

        if shortfall_count == 0 and unallocated_count == 0:
            return "✅ 실제 Upbit 잔고와 전략 기록이 모두 일치합니다.", None
        if shortfall_count:
            lines.extend(["", "💡 차감 버튼은 부족한 전략 기록만 조정합니다.", "ℹ️ 실제 Upbit 주문은 실행되지 않습니다."])
        return "\n".join(lines), {"inline_keyboard": buttons} if buttons else None
    finally:
        db.close()


def _apply_sync_callback(
    chat_id: str,
    action: str,
    currency: str,
    subscription_id: int,
) -> str:
    """버튼을 누른 시점의 최신 차이만 선택 전략에 반영합니다."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
        if user is None:
            raise PositionSyncError("Telegram 연동 정보를 찾을 수 없습니다.")
        accounts = _accounts_for_user(db, user.id)
        positions = recorded_strategy_positions(db, user.id)
        selected = next(
            (
                item for item in positions
                if item.subscription.id == subscription_id
                and item.market.endswith(f"-{currency}")
            ),
            None,
        )
        if selected is None:
            raise PositionSyncError("선택한 실전 전략을 찾을 수 없습니다.")

        actual_total = actual_coin_totals(accounts).get(currency, 0.0)
        recorded_total = recorded_strategy_volumes(db, user.id).get(currency, 0.0)
        difference = actual_total - recorded_total
        item_status, _ = reconciliation_status(actual_total, recorded_total)
        if item_status == "matched":
            return f"ℹ️ {currency} 잔고는 이미 실제 Upbit 잔고와 동기화되어 있습니다."
        if action not in {"deduct", "sell"} or difference >= 0:
            raise PositionSyncError("실제 잔고 부족분만 전략에서 차감할 수 있습니다.")
        volume = min(-difference, selected.volume)
        adjustment = apply_position_sync(
            db,
            user_id=user.id,
            accounts=accounts,
            subscription_id=subscription_id,
            action=action,
            volume=volume,
            source="telegram",
        )
        return f"✅ {currency} {adjustment.volume:.8f}개를 {selected.strategy.name} 전략에서 차감했습니다."
    finally:
        db.close()


class TelegramPoller:
    """Telegram getUpdates를 사용해 `/start 연동코드` 명령을 처리합니다."""

    def __init__(self, token: str):
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._offset: int | None = None
        self._pending: dict[str, PendingCommand] = {}

    async def _send_message(
        self,
        client: httpx.AsyncClient,
        chat_id: str,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        """동일 HTTP 클라이언트로 Telegram 메시지를 전송합니다."""
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        response = await client.post(
            f"{self._base_url}/sendMessage",
            json=payload,
        )
        response.raise_for_status()

    async def _answer_callback(self, client: httpx.AsyncClient, callback_id: str, text: str) -> None:
        """Telegram 버튼의 로딩 표시를 끝내고 처리 결과를 짧게 알립니다."""
        response = await client.post(
            f"{self._base_url}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text[:180]},
        )
        response.raise_for_status()

    async def _remove_inline_keyboard(
        self,
        client: httpx.AsyncClient,
        chat_id: str,
        message_id: int,
    ) -> None:
        """처리 완료된 동기화 메시지의 버튼을 제거해 중복 실행을 막습니다."""
        response = await client.post(
            f"{self._base_url}/editMessageReplyMarkup",
            json={"chat_id": chat_id, "message_id": message_id, "reply_markup": {"inline_keyboard": []}},
        )
        response.raise_for_status()

    async def _handle_update(self, client: httpx.AsyncClient, update: dict) -> None:
        """한 건의 Telegram 명령 또는 포지션 동기화 버튼을 처리합니다."""
        callback = update.get("callback_query") or {}
        if callback:
            callback_id = str(callback.get("id") or "")
            data = str(callback.get("data") or "")
            callback_message = callback.get("message") or {}
            chat_id = str((callback_message.get("chat") or {}).get("id") or "")
            message_id = int(callback_message.get("message_id") or 0)
            if callback_id and chat_id and data.startswith("psync|"):
                try:
                    _, action, currency, subscription_id = data.split("|", maxsplit=3)
                    reply = await asyncio.to_thread(
                        _apply_sync_callback,
                        chat_id,
                        action,
                        currency,
                        int(subscription_id),
                    )
                    await self._answer_callback(client, callback_id, "동기화 완료")
                    if message_id:
                        try:
                            await self._remove_inline_keyboard(client, chat_id, message_id)
                        except Exception as error:
                            logger.warning(
                                "Telegram sync keyboard removal failed: %s",
                                type(error).__name__,
                            )
                except (PositionSyncError, ValueError) as error:
                    reply = f"동기화하지 못했습니다: {error}"
                    await self._answer_callback(client, callback_id, "동기화 실패")
                except Exception:
                    logger.exception("Telegram position sync callback failed")
                    reply = "동기화 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
                    await self._answer_callback(client, callback_id, "동기화 실패")
                await self._send_message(client, chat_id, reply)
            return

        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        chat_type = str(chat.get("type") or "private")
        if not chat_id:
            return

        first_token = text.split(maxsplit=1)[0]
        command = first_token.split("@", maxsplit=1)[0].lower()

        if command == "/start":
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                await self._send_message(
                    client,
                    chat_id,
                    "🔗 SignalTrade 대시보드에서 연동 코드를 발급한 뒤\n"
                    "/start ABCD2345 형식으로 입력해 주세요.",
                )
                return

            linked = await asyncio.to_thread(_link_chat, parts[1].strip(), chat_id)
            if linked:
                reply = (
                    "✅ SignalTrade 연동이 완료되었습니다!\n\n"
                    "🔔 자동매매 체결과 주요 상태를 여기에서 알려드릴게요.\n"
                    "명령어를 확인하려면 /help를 입력해 주세요."
                )
            else:
                reply = (
                    "❌ 연동 코드가 올바르지 않거나 만료되었습니다.\n"
                    "SignalTrade 대시보드에서 새 코드를 발급해 주세요."
                )
            await self._send_message(client, chat_id, reply)
            return

        if command == "/help":
            self._pending.pop(chat_id, None)
            await self._send_message(client, chat_id, _help_text())
            return

        if command in {"/chatid", "/findid"}:
            if chat_type != "private":
                reply = "🔒 아이디 찾기는 텔레그램 봇과의 개인 채팅에서만 사용할 수 있습니다."
            else:
                reply = await asyncio.to_thread(_find_id_text, chat_id)
            await self._send_message(client, chat_id, reply)
            return

        if command == "/cancel":
            pending = self._pending.pop(chat_id, None)
            reply = "✅ 진행 중인 명령을 취소했습니다." if pending else "ℹ️ 취소할 명령이 없습니다."
            await self._send_message(client, chat_id, reply)
            return

        if command in {"/pause", "/resume"}:
            action = command.removeprefix("/")
            reply = await asyncio.to_thread(_strategy_menu, chat_id, action)
            if "가능한" in reply:
                self._pending[chat_id] = PendingCommand(
                    action=action,
                    expires_at=datetime.utcnow() + COMMAND_TIMEOUT,
                )
            else:
                self._pending.pop(chat_id, None)
            await self._send_message(client, chat_id, reply)
            return

        if command == "/status":
            await self._send_message(client, chat_id, await asyncio.to_thread(_status_text, chat_id))
            return

        if command == "/balance":
            try:
                reply = await asyncio.to_thread(_balance_text, chat_id)
            except Exception:
                logger.exception("Telegram balance lookup failed")
                reply = "❌ 잔고를 조회하지 못했습니다.\nAPI Key와 Upbit 허용 IP를 확인해 주세요."
            await self._send_message(client, chat_id, reply)
            return

        if command == "/positions":
            await self._send_message(client, chat_id, await asyncio.to_thread(_positions_text, chat_id))
            return

        if command == "/close":
            reply = await asyncio.to_thread(_close_menu, chat_id)
            if "매도할 포지션을 선택" in reply:
                self._pending[chat_id] = PendingCommand(
                    action="close_select",
                    expires_at=datetime.utcnow() + COMMAND_TIMEOUT,
                )
            else:
                self._pending.pop(chat_id, None)
            await self._send_message(client, chat_id, reply)
            return

        if command == "/sync":
            try:
                reply, keyboard = await asyncio.to_thread(_sync_menu, chat_id)
            except Exception:
                logger.exception("Telegram position sync lookup failed")
                reply, keyboard = "❌ 잔고를 조회하지 못했습니다.\nAPI Key와 Upbit 허용 IP를 확인해 주세요.", None
            await self._send_message(client, chat_id, reply, keyboard)
            return

        pending = self._pending.get(chat_id)
        if pending and pending.expires_at <= datetime.utcnow():
            self._pending.pop(chat_id, None)
            pending = None
        if pending and command.startswith("/"):
            selection = command.removeprefix("/")
            if pending.action in {"pause", "resume"}:
                reply = await asyncio.to_thread(
                    _set_pause,
                    chat_id,
                    pending.action,
                    selection,
                )
                if not reply.startswith("⚠️"):
                    self._pending.pop(chat_id, None)
            elif pending.action == "close_select":
                reply, strategy_ids = await asyncio.to_thread(
                    _prepare_close,
                    chat_id,
                    selection,
                )
                if strategy_ids:
                    self._pending[chat_id] = PendingCommand(
                        action="close_confirm",
                        expires_at=datetime.utcnow() + COMMAND_TIMEOUT,
                        strategy_ids=strategy_ids,
                    )
            elif pending.action == "close_confirm" and command == "/confirm":
                self._pending.pop(chat_id, None)
                reply = await _execute_close(chat_id, pending.strategy_ids)
            else:
                reply = "⚠️ /confirm으로 매도를 실행하거나 /cancel로 취소해 주세요."
            await self._send_message(client, chat_id, reply)
            return

        if text.startswith("/"):
            await self._send_message(
                client,
                chat_id,
                "❓ 등록되지 않은 명령어입니다.\n사용 가능한 명령을 확인하려면 /help를 입력해 주세요.",
            )

    async def run(self, stop_event: asyncio.Event) -> None:
        """long polling을 유지하며 종료 이벤트가 오면 안전하게 빠져나옵니다."""
        timeout = httpx.Timeout(35.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info("Telegram polling started")
            while not stop_event.is_set():
                try:
                    response = await client.get(
                        f"{self._base_url}/getUpdates",
                        params={"offset": self._offset, "timeout": 25},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if not payload.get("ok"):
                        raise RuntimeError(payload.get("description", "Telegram API error"))

                    for update in payload.get("result", []):
                        self._offset = int(update["update_id"]) + 1
                        await self._handle_update(client, update)
                except asyncio.CancelledError:
                    raise
                except httpx.HTTPStatusError as error:
                    # 요청 URL에는 봇 토큰이 포함되므로 상태 코드와 Telegram 설명만 기록합니다.
                    try:
                        description = error.response.json().get("description", "Telegram API error")
                    except ValueError:
                        description = "Telegram API error"
                    logger.warning(
                        "Telegram polling failed: status=%s description=%s",
                        error.response.status_code,
                        description,
                    )
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass
                except Exception as error:
                    # httpx 예외에는 봇 토큰이 포함된 요청 URL이 들어갈 수 있으므로
                    # 예외 문자열 전체를 로그로 남기지 않습니다.
                    logger.warning("Telegram polling failed: %s", type(error).__name__)
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass


async def run_telegram_poller(stop_event: asyncio.Event) -> None:
    """토큰이 설정된 환경에서만 Telegram polling을 시작합니다."""
    if not settings.telegram_bot_token:
        logger.info("Telegram polling disabled: TELEGRAM_BOT_TOKEN is empty")
        return
    await TelegramPoller(settings.telegram_bot_token).run(stop_event)
