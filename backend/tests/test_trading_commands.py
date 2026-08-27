from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.messaging.envelope import MessageEnvelope
from app.messaging.sqs import QueueMessage
from app.messaging.trading_commands import execute_strategy_signal
from app.trading.worker import process_message


def _envelope(**payload: object) -> MessageEnvelope:
    return MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        payload={
            "signal_id": 41,
            "target_user_id": 7,
            "target_mode": "live",
            **payload,
        },
    )


def test_execute_strategy_signal_preserves_target_scope() -> None:
    with patch(
        "app.messaging.trading_commands.dispatch_signal",
        new=AsyncMock(return_value=1),
    ) as dispatcher:
        result = asyncio.run(execute_strategy_signal(_envelope()))

    dispatcher.assert_awaited_once_with(41, user_id=7, mode="live")
    assert result.signal_id == 41
    assert result.execution_count == 1


@pytest.mark.parametrize(
    ("payload", "message_type"),
    [
        ({"signal_id": 0}, "StrategySignalCreated"),
        ({"target_user_id": -1}, "StrategySignalCreated"),
        ({"target_mode": "unknown"}, "StrategySignalCreated"),
        ({}, "UnknownMessage"),
    ],
)
def test_execute_strategy_signal_rejects_invalid_messages(
    payload: dict[str, object],
    message_type: str,
) -> None:
    envelope = _envelope(**payload).model_copy(update={"message_type": message_type})
    with pytest.raises(ValueError):
        asyncio.run(execute_strategy_signal(envelope))


def test_process_message_acknowledges_only_after_success() -> None:
    queue = Mock()
    message = QueueMessage("receipt", _envelope(), 1)

    with patch(
        "app.trading.worker.execute_strategy_signal",
        new=AsyncMock(return_value=Mock(
            signal_id=41,
            target_user_id=7,
            target_mode="live",
            execution_count=1,
        )),
    ):
        process_message(queue, message)

    queue.acknowledge.assert_called_once_with(message)


def test_process_message_leaves_failed_message_unacknowledged() -> None:
    queue = Mock()
    message = QueueMessage("receipt", _envelope(), 1)

    with patch(
        "app.trading.worker.execute_strategy_signal",
        new=AsyncMock(side_effect=RuntimeError("temporary failure")),
    ), pytest.raises(RuntimeError):
        process_message(queue, message)

    queue.acknowledge.assert_not_called()
