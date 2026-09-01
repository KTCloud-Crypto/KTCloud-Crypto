from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.user import User
from app.identity import SimpleRateLimiter
from app.notification.identity_client import link_telegram_chat
from app.notification.portfolio_client import get_open_positions, get_user_balance
from app.notification.strategy_client import set_subscriptions_paused
from app.notification.trading_client import request_manual_liquidations

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
        updated = set_subscriptions_paused(
            user_id=user.id,
            subscription_ids=[item[0].id for item in candidates],
            paused=target_paused,
        )
        if updated is None:
            return "⚠️ 전략 상태 변경에 실패했습니다. 잠시 후 다시 시도해 주세요."
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
        accounts = get_user_balance(user.id)
        if accounts is None:
            return "⚠️ 잔고를 조회하지 못했습니다. 잠시 후 다시 시도해 주세요."
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
        positions = get_open_positions(user.id)
        if positions is None:
            return "⚠️ 포지션을 조회하지 못했습니다. 잠시 후 다시 시도해 주세요."
        found = False
        for position in positions:
            found = True
            lines.append(
                f"\n📈 {position['strategy_name']}\n"
                f"   종목: {position['market']}\n"
                f"   수량: {float(position['volume']):.8f}\n"
                f"   평균 매수가: {float(position.get('average_buy_price') or 0):,.0f}원"
            )
        if not found:
            lines.append("\n📭 현재 보유한 전략 포지션이 없습니다.")
        return "\n".join(lines)
    finally:
        db.close()


def _close_command(position: dict) -> str:
    prefix = "paper" if position["mode"] == "simulated" else "live"
    symbol = str(position["market"]).split("-", maxsplit=1)[-1].lower()
    code = str(position["strategy_code"])
    return f"{prefix}_{symbol}_{STRATEGY_ALIASES.get(code, code.removesuffix('_v1'))}"


def _close_candidates(user: User) -> list[dict]:
    return get_open_positions(user.id) or []


def _close_menu(chat_id: str) -> str:
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        candidates = _close_candidates(user)
        if not candidates:
            return "📭 전량 매도할 전략 포지션이 없습니다."
        lines = [
            "🚨 [포지션 전량 매도]",
            "",
            "매도할 포지션을 선택해 주세요.",
            "",
        ]
        for position in candidates:
            mode = "모의" if position["mode"] == "simulated" else "실전"
            lines.append(
                f"/{_close_command(position)} - [{mode}] "
                f"{position['market']} · {position['strategy_name']} · {float(position['volume']):.8f}"
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
        candidates = _close_candidates(user)
        if selection != "all":
            candidates = [
                item
                for item in candidates
                if _close_command(item) == selection
            ]
        if not candidates:
            return "⚠️ 선택할 수 없는 포지션입니다. 표시된 명령을 입력하거나 /cancel로 취소해 주세요.", ()

        lines = ["⚠️ [전량 매도 최종 확인]", ""]
        for position in candidates:
            mode = "모의" if position["mode"] == "simulated" else "실전"
            lines.append(
                f"• [{mode}] {position['market']} · {position['strategy_name']}: "
                f"{float(position['volume']):.8f}"
            )
        lines.extend([
            "",
            "선택한 포지션을 시장가로 전량 매도합니다.",
            "/confirm - 매도 실행",
            "/cancel - 취소",
        ])
        return "\n".join(lines), tuple(int(item["subscription_id"]) for item in candidates)
    finally:
        db.close()


async def _execute_close(chat_id: str, strategy_ids: tuple[int, ...]) -> str:
    """확인된 수동 청산 요청을 Trading service에 전달합니다."""
    db = SessionLocal()
    try:
        user = _linked_user(db, chat_id)
        if user is None:
            return "🔗 먼저 SignalTrade 대시보드에서 Telegram을 연동해 주세요."
        user_id = user.id
    finally:
        db.close()

    result = await request_manual_liquidations(
        user_id=user_id,
        subscription_ids=list(strategy_ids),
    )
    if result is None:
        return "⚠️ 전량 매도 요청 전달에 실패했습니다. 잠시 후 다시 시도해 주세요."
    requested, failures = result

    if failures:
        return (
            f"⚠️ 전량 매도 요청 {requested}건을 전달했습니다.\n"
            f"❌ 처리하지 못한 전략: {', '.join(failures)}\n"
            "체결 결과는 별도 Telegram 알림에서 확인해 주세요."
        )
    if requested == 0:
        return "📭 매도할 포지션이 없거나 이미 청산되었습니다."
    return (
        f"✅ 전량 매도 요청 {requested}건을 전달했습니다.\n"
        "체결 결과는 별도 Telegram 알림에서 확인해 주세요."
    )


def _link_chat(code: str, chat_id: str) -> bool:
    """Telegram 연결 command를 Identity API에 전달합니다."""
    return link_telegram_chat(code, chat_id)


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
    ) -> None:
        """동일 HTTP 클라이언트로 Telegram 메시지를 전송합니다."""
        payload = {"chat_id": chat_id, "text": text}
        response = await client.post(
            f"{self._base_url}/sendMessage",
            json=payload,
        )
        response.raise_for_status()

    async def _handle_update(self, client: httpx.AsyncClient, update: dict) -> None:
        """한 건의 Telegram 명령을 처리합니다."""
        if update.get("callback_query"):
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
