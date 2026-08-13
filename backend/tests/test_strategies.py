import uuid
import asyncio
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.api_key import ApiKey
from app.models.strategy import UserStrategy
from app.models.strategy_signal import StrategyExecution, StrategySignal
from app.models.user import User
from app.models.paper_account import PaperAccount, PaperLedger
from app.services.execution_preflight import PreflightResult
from app.services.security import create_jwt_token, hash_password
from app.services.signal_dispatcher import dispatch_signal


client = TestClient(app)


def test_strategy_can_be_selected_and_disabled() -> None:
    db = SessionLocal()
    user = User(
        username=f"strategy_test_{uuid.uuid4().hex}",
        password=hash_password("test-password-123"),
        nickname="전략테스트",
        # 자동매매 실행 여부는 전략 구독 상태로 결정되며 이 레거시 필드와 무관합니다.
        bot_enabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_jwt_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_delta=timedelta(minutes=5),
        token_type="access",
    )
    headers = {"Authorization": f"Bearer {token}"}
    signal_ids = []

    try:
        response = client.get("/strategies", headers=headers)
        assert response.status_code == 200
        catalog = response.json()
        assert {item["code"] for item in catalog} == {
            "sma_cross_v1",
            "rsi_reversal_v1",
            "macd_cross_v1",
            "bollinger_reentry_v1",
            "donchian_breakout_v1",
            "rsi_macd_confirm_v1",
            "bollinger_squeeze_breakout_v1",
            "volatility_breakout_v1",
        }
        assert all(item["parameters"] for item in catalog)
        strategy = next(item for item in catalog if item["code"] == "sma_cross_v1")
        assert strategy["selected"] is False
        assert strategy["invest_ratio"] == 0
        assert strategy["selected_timeframe_minutes"] == 0

        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True},
        )
        assert response.status_code == 422
        assert "분봉" in response.json()["detail"]

        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "timeframe_minutes": 5},
        )
        assert response.status_code == 422
        assert "투자 비율" in response.json()["detail"]

        response = client.put(
            "/paper-account",
            headers=headers,
            json={"target_net_deposit": 100_000},
        )
        assert response.status_code == 200
        assert response.json()["cash_balance"] == 100_000

        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        assert response.json()["selected"] is True
        assert response.json()["invest_ratio"] == 0.2
        assert response.json()["selected_timeframe_minutes"] == 5
        assert response.json()["allowed_timeframes"] == [1, 3, 5, 10, 15, 30, 60, 240]
        assert response.json()["paused"] is False

        # 설정 저장은 Telegram 일시정지를 유지하지만, 해제 후 재선택하면 재개합니다.
        subscription = (
            db.query(UserStrategy)
            .filter(
                UserStrategy.user_id == user.id,
                UserStrategy.strategy_id == strategy["id"],
                UserStrategy.mode == "simulated",
            )
            .one()
        )
        subscription.paused = True
        db.commit()
        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.json()["paused"] is True
        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": False, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        assert response.json()["paused"] is False

        # 같은 전략도 실전 모드에는 별도 설정으로 저장됩니다.
        response = client.get("/strategies?mode=live", headers=headers)
        live_strategy = next(item for item in response.json() if item["code"] == "sma_cross_v1")
        assert live_strategy["selected"] is False
        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=live",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.1, "timeframe_minutes": 10},
        )
        assert response.status_code == 409
        assert "API Key" in response.json()["detail"]

        db.add(ApiKey(
            user_id=user.id,
            encrypted_access_key="test-access",
            encrypted_secret_key="test-secret",
        ))
        db.commit()
        with patch(
            "app.api.strategies.available_krw_balance",
            return_value=Decimal("100000"),
        ) as balance_mock:
            response = client.get("/strategies?mode=live", headers=headers)
            assert response.status_code == 200
            assert balance_mock.call_count == 1
            response = client.put(
                f"/strategies/{strategy['id']}/subscription?mode=live",
                headers=headers,
                json={"enabled": True, "invest_ratio": 0.1, "timeframe_minutes": 10},
            )
        assert response.status_code == 200
        assert response.json()["selected"] is True
        assert response.json()["invest_ratio"] == 0.1

        # 레거시 bot_enabled 값과 무관하게 활성화된 실전 전략의 매수·매도
        # 신호가 실제 주문 단계까지 전달되는지 확인합니다.
        user.live_trading_enabled = True
        db.commit()
        live_signals = []
        for action in ("buy", "sell"):
            live_signal = StrategySignal(
                strategy_id=strategy["id"],
                market="KRW-BTC",
                timeframe_minutes=10,
                action=action,
                source="test",
                candle_open_time=datetime.utcnow(),
                close_price=100_000_000,
                metrics={"test_price": 100_000_000},
            )
            db.add(live_signal)
            db.commit()
            db.refresh(live_signal)
            signal_ids.append(live_signal.id)
            live_signals.append(live_signal)

        with (
            patch(
                "app.services.signal_dispatcher._prepare_live_execution",
                side_effect=[
                    PreflightResult(True, 10_000),
                    PreflightResult(True, 10_000, order_volume=0.0001),
                ],
            ),
            patch("app.services.signal_dispatcher._place_live_order") as place_live_order,
            patch("app.services.signal_dispatcher._notify"),
        ):
            for live_signal in live_signals:
                assert asyncio.run(dispatch_signal(live_signal.id, user_id=user.id)) == 1

        assert [call.args[1].action for call in place_live_order.call_args_list] == ["buy", "sell"]

        response = client.get("/strategies?mode=simulated", headers=headers)
        paper_strategy = next(item for item in response.json() if item["code"] == "sma_cross_v1")
        assert paper_strategy["invest_ratio"] == 0.2
        assert paper_strategy["selected_timeframe_minutes"] == 5

        second_strategy = next(item for item in catalog if item["code"] == "rsi_reversal_v1")
        response = client.put(
            f"/strategies/{second_strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.9, "timeframe_minutes": 5},
        )
        # 예산은 항상 가용 현금 안에서만 산정되므로 비율 합계 상한을 두지 않습니다.
        assert response.status_code == 200
        assert response.json()["invest_ratio"] == 0.9

        response = client.get("/strategies", headers=headers)
        selected = next(item for item in response.json() if item["code"] == "sma_cross_v1")
        assert selected["selected"] is True
        assert selected["selected_timeframe_minutes"] == 5

        signal = StrategySignal(
            strategy_id=strategy["id"],
            market="KRW-BTC",
            timeframe_minutes=5,
            action="buy",
            source="test",
            candle_open_time=datetime.utcnow(),
            close_price=100_000_000,
            metrics={"test_price": 100_000_000},
        )
        db.add(signal)
        db.commit()
        db.refresh(signal)
        signal_ids.append(signal.id)

        assert asyncio.run(dispatch_signal(signal.id, user_id=user.id)) == 1
        assert asyncio.run(dispatch_signal(signal.id, user_id=user.id)) == 0
        execution = db.query(StrategyExecution).filter(StrategyExecution.signal_id == signal.id).one()
        assert execution.user_id == user.id
        assert execution.status == "simulated_success"
        assert execution.executed_volume > 0

        # 첫 전략이 매수를 마쳐 현금이 줄었으므로,
        # 두 번째 전략은 남은 현금의 20%를 배정받습니다.
        response = client.put(
            f"/strategies/{second_strategy['id']}/subscription",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        second_signal = StrategySignal(
            strategy_id=second_strategy["id"],
            market="KRW-BTC",
            timeframe_minutes=5,
            action="buy",
            source="test",
            candle_open_time=datetime.utcnow(),
            close_price=100_000_000,
            metrics={"test_price": 100_000_000},
        )
        db.add(second_signal)
        db.commit()
        db.refresh(second_signal)
        signal_ids.append(second_signal.id)
        assert asyncio.run(dispatch_signal(second_signal.id, user_id=user.id)) == 1
        second_execution = (
            db.query(StrategyExecution)
            .filter(StrategyExecution.signal_id == second_signal.id)
            .one()
        )
        assert second_execution.status == "simulated_success"
        assert second_execution.order_amount == 15_992

        duplicate_buy_signal = StrategySignal(
            strategy_id=strategy["id"],
            market="KRW-BTC",
            timeframe_minutes=5,
            action="buy",
            source="test",
            candle_open_time=datetime.utcnow(),
            close_price=100_000_000,
            metrics={"test_price": 100_000_000},
        )
        db.add(duplicate_buy_signal)
        db.commit()
        db.refresh(duplicate_buy_signal)
        signal_ids.append(duplicate_buy_signal.id)
        assert asyncio.run(dispatch_signal(duplicate_buy_signal.id, user_id=user.id)) == 1
        skipped_execution = (
            db.query(StrategyExecution)
            .filter(StrategyExecution.signal_id == duplicate_buy_signal.id)
            .one()
        )
        assert skipped_execution.status == "simulated_skipped"
        assert skipped_execution.notification_sent is False

        response = client.get("/strategies/positions", headers=headers)
        assert response.status_code == 200
        position = next(item for item in response.json() if item["strategy_code"] == "sma_cross_v1")
        assert position["status"] == "flat"
        assert position["volume"] == 0
        assert position["paper_status"] == "holding"
        assert position["paper_volume"] > 0

        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=simulated",
            headers=headers,
            json={"enabled": False, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 409
        assert "먼저 매도" in response.json()["detail"]

        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=simulated",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 10},
        )
        assert response.status_code == 409
        assert "분봉" in response.json()["detail"]

        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=simulated",
            headers=headers,
            json={
                "enabled": True,
                "invest_ratio": 0.15,
                "timeframe_minutes": 5,
                "stop_loss_rate": 0.05,
                "take_profit_rate": 0.1,
            },
        )
        assert response.status_code == 200
        assert response.json()["invest_ratio"] == 0.15
        assert response.json()["stop_loss_rate"] == 0.05
        assert response.json()["take_profit_rate"] == 0.1

        response = client.get("/strategies/executions", headers=headers)
        assert response.status_code == 200
        listed_execution = next(item for item in response.json() if item["id"] == execution.id)
        assert listed_execution["strategy_code"] == "sma_cross_v1"
        assert listed_execution["mode"] == "simulated"
        assert listed_execution["status"] == "simulated_success"

        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=simulated",
            headers=headers,
            json={
                "enabled": False,
                "force_disable": True,
                "invest_ratio": 0.15,
                "timeframe_minutes": 5,
            },
        )
        assert response.status_code == 200
        assert response.json()["selected"] is False
        assert response.json()["has_open_position"] is True

        with patch(
            "app.api.strategies.get_current_price",
            new=AsyncMock(return_value=100_000_000),
        ):
            response = client.post(
                f"/strategies/{strategy['id']}/manual-sell?mode=simulated",
                headers=headers,
            )
        assert response.status_code == 200
        sell_signal_id = response.json()["signal_id"]
        signal_ids.append(sell_signal_id)
        sell_execution = (
            db.query(StrategyExecution)
            .filter(StrategyExecution.signal_id == sell_signal_id)
            .one()
        )
        assert sell_execution.status == "simulated_success"

        response = client.get("/strategies?mode=simulated", headers=headers)
        disabled_strategy = next(
            item for item in response.json() if item["code"] == "sma_cross_v1"
        )
        assert disabled_strategy["selected"] is False
        assert disabled_strategy["has_open_position"] is False

        response = client.get("/strategies/positions", headers=headers)
        position = next(
            item for item in response.json() if item["strategy_code"] == "sma_cross_v1"
        )
        assert position["paper_status"] == "flat"

        response = client.put(
            f"/strategies/{strategy['id']}/subscription?mode=simulated",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.15, "timeframe_minutes": 5},
        )
        assert response.status_code == 200

        empty_sell_signal = StrategySignal(
            strategy_id=strategy["id"],
            market="KRW-BTC",
            timeframe_minutes=5,
            action="sell",
            source="test",
            candle_open_time=datetime.utcnow(),
            close_price=100_000_000,
            metrics={"test_price": 100_000_000},
        )
        db.add(empty_sell_signal)
        db.commit()
        db.refresh(empty_sell_signal)
        signal_ids.append(empty_sell_signal.id)
        assert asyncio.run(dispatch_signal(empty_sell_signal.id, user_id=user.id)) == 1
        empty_sell_execution = (
            db.query(StrategyExecution)
            .filter(StrategyExecution.signal_id == empty_sell_signal.id)
            .one()
        )
        assert empty_sell_execution.status == "simulated_skipped"
        assert empty_sell_execution.notification_sent is False

        response = client.put(
            "/paper-account",
            headers=headers,
            json={"target_net_deposit": 0},
        )
        assert response.status_code == 409

        response = client.get("/strategies/signals", headers=headers)
        assert response.status_code == 200
        listed_signal = next(item for item in response.json() if item["id"] == signal.id)
        assert listed_signal["timeframe_minutes"] == 5
        assert listed_signal["action"] == "buy"
        assert listed_signal["source"] == "test"

        response = client.put(
            f"/strategies/{strategy['id']}/subscription",
            headers=headers,
            json={"enabled": False, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        assert response.json()["selected"] is False
    finally:
        account = db.query(PaperAccount).filter(PaperAccount.user_id == user.id).first()
        if account is not None:
            db.query(PaperLedger).filter(PaperLedger.account_id == account.id).delete()
        if signal_ids:
            db.query(StrategyExecution).filter(StrategyExecution.signal_id.in_(signal_ids)).delete(
                synchronize_session=False
            )
            db.query(StrategySignal).filter(StrategySignal.id.in_(signal_ids)).delete(
                synchronize_session=False
            )
        db.query(UserStrategy).filter(UserStrategy.user_id == user.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.query(PaperAccount).filter(PaperAccount.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()
