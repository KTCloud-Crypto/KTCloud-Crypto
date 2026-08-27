"""worker 중단으로 준비 상태에 멈춘 실행 레코드를 안전하게 복구합니다."""

import logging
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.api_key import ApiKey
from app.models.strategy import Strategy, UserStrategy
from app.models.strategy_signal import StrategyExecution
from app.models.user import User
from app.identity import resolve_exchange_credentials
from app.portfolio.position_reconciliation import actual_coin_totals, recorded_strategy_volumes
from app.notification.telegram import send_message
from app.market_data import get_accounts

logger = logging.getLogger(__name__)


def live_recovery_status(action: str, difference: float) -> str:
    """잔고 차이 방향으로 실제 체결 가능성을 분류합니다."""
    tolerance = max(1e-8, abs(difference) * 1e-6)
    if action == "buy" and difference > tolerance:
        return "uncertain"
    if action == "sell" and difference < -tolerance:
        return "uncertain"
    return "failed"


def recover_stale_executions() -> tuple[int, int]:
    """오래된 준비 상태를 정리하고 (정리 수, 확인 필요 수)를 반환합니다."""
    db = SessionLocal()
    recovered = 0
    uncertain_count = 0
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=max(30, settings.stale_execution_seconds))
        rows = (
            db.query(StrategyExecution, UserStrategy, Strategy, User)
            .join(UserStrategy, UserStrategy.id == StrategyExecution.user_strategy_id)
            .join(Strategy, Strategy.id == UserStrategy.strategy_id)
            .join(User, User.id == StrategyExecution.user_id)
            .filter(
                StrategyExecution.status.in_(["ready", "simulated_pending"]),
                StrategyExecution.created_at < cutoff,
            )
            .all()
        )
        account_cache: dict[int, tuple[dict[str, float], dict[str, float]]] = {}
        for execution, _, strategy, user in rows:
            if execution.status == "simulated_pending":
                execution.status = "simulated_failed"
                execution.error_message = "worker가 중단되어 완료되지 않은 모의 주문을 정리했습니다."
                recovered += 1
                continue

            try:
                if user.id not in account_cache:
                    api_key = db.query(ApiKey).filter(ApiKey.user_id == user.id).one()
                    access_key, secret_key = resolve_exchange_credentials(api_key)
                    accounts = get_accounts(
                        access_key=access_key,
                        secret_key=secret_key,
                        base_url=settings.upbit_api_base_url,
                    )
                    account_cache[user.id] = (
                        actual_coin_totals(accounts),
                        recorded_strategy_volumes(db, user.id),
                    )
                actual, recorded = account_cache[user.id]
                currency = execution.market.split("-", maxsplit=1)[-1]
                difference = actual.get(currency, 0.0) - recorded.get(currency, 0.0)
                execution.status = live_recovery_status(execution.action, difference)
                if execution.status == "uncertain":
                    execution.error_message = "worker 중단 중 실제 주문이 체결됐을 가능성이 있어 잔고 동기화가 필요합니다."
                    uncertain_count += 1
                    send_message(
                        user.telegram_chat_id,
                        "\n".join([
                            "⚠️ [실전 주문 상태 확인 필요]",
                            f"📌 전략: {strategy.name}",
                            f"🪙 종목: {execution.market}",
                            f"↔️ 구분: {'매수' if execution.action == 'buy' else '매도'}",
                            "worker 중단 중 실제 체결됐을 가능성이 있습니다.",
                            "🔄 웹의 실전계좌 화면에서 잔고 차이를 확인해 주세요.",
                            "🛡️ 확인 전에는 같은 방향의 주문을 추가 실행하지 않습니다.",
                        ]),
                    )
                else:
                    execution.error_message = "worker가 중단되어 제출 여부를 확인할 수 없었으나 잔고 차이는 없습니다."
                recovered += 1
            except Exception as error:
                logger.warning(
                    "Stale live execution recovery failed: execution_id=%s error=%s",
                    execution.id,
                    type(error).__name__,
                )
        db.commit()
        return recovered, uncertain_count
    finally:
        db.close()
