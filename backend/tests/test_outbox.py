from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.messaging.envelope import MessageEnvelope
from app.messaging.outbox import OutboxPublisher, enqueue_outbox
from app.messaging.strategy_events import enqueue_strategy_signal_created
from app.models.message_outbox import MessageOutbox
from app.models.strategy_signal import StrategySignal


class FakeQueue:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.published: list[MessageEnvelope] = []

    def publish(self, envelope: MessageEnvelope, *, delay_seconds: int = 0) -> str:
        if self.error is not None:
            raise self.error
        self.published.append(envelope)
        return "transport-message-1"


def make_session():
    engine = create_engine("sqlite://")
    MessageOutbox.__table__.create(engine)
    return sessionmaker(bind=engine)()


def make_signal_session():
    engine = create_engine("sqlite://")
    StrategySignal.__table__.create(engine)
    MessageOutbox.__table__.create(engine)
    return sessionmaker(bind=engine)()


def test_strategy_signal_event_is_added_to_the_same_transaction() -> None:
    db = make_signal_session()
    signal = StrategySignal(
        strategy_id=7,
        market="KRW-BTC",
        timeframe_minutes=5,
        action="buy",
        source="engine",
        candle_open_time=datetime(2026, 8, 26, 1, 5),
        close_price=100_000_000,
        metrics={"short_sma": 99_000_000},
    )
    db.add(signal)

    message = enqueue_strategy_signal_created(db, signal)

    assert signal.id is not None
    assert message.message_type == "StrategySignalCreated"
    assert message.idempotency_key == f"strategy-signal:{signal.id}"
    assert message.payload == {
        "signal_id": signal.id,
        "strategy_id": 7,
        "market": "KRW-BTC",
        "timeframe_minutes": 5,
        "action": "buy",
        "source": "engine",
        "candle_open_time": "2026-08-26T01:05:00",
        "close_price": 100_000_000,
        "metrics": {"short_sma": 99_000_000},
        "target_user_id": None,
        "target_mode": None,
    }
    assert db.query(StrategySignal).count() == 1
    assert db.query(MessageOutbox).count() == 1

    db.rollback()

    assert db.query(StrategySignal).count() == 0
    assert db.query(MessageOutbox).count() == 0


def test_enqueue_outbox_preserves_envelope_without_committing() -> None:
    db = make_session()
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        correlation_id="signal-10",
        idempotency_key="strategy-signal:10",
        payload={"signal_id": 10},
    )

    message = enqueue_outbox(db, envelope)

    assert message.id is not None
    assert message.status == "pending"
    assert message.to_envelope() == envelope
    assert db.query(MessageOutbox).count() == 1


def test_outbox_publisher_marks_successful_message_as_published() -> None:
    db = make_session()
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        payload={"signal_id": 11},
    )
    message = enqueue_outbox(db, envelope)
    queue = FakeQueue()
    now = datetime.now(timezone.utc) + timedelta(seconds=1)

    result = OutboxPublisher(queue).publish_pending(db, now=now)

    assert result.selected == 1
    assert result.published == 1
    assert result.failed == 0
    assert queue.published == [envelope]
    assert message.status == "published"
    assert message.attempt_count == 1
    assert message.transport_message_id == "transport-message-1"
    assert message.published_at == now


def test_outbox_publisher_records_failure_and_delays_retry() -> None:
    db = make_session()
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        payload={"signal_id": 12},
    )
    message = enqueue_outbox(db, envelope)
    queue = FakeQueue(error=RuntimeError("queue unavailable"))
    now = datetime.now(timezone.utc) + timedelta(seconds=1)

    result = OutboxPublisher(queue).publish_pending(db, now=now)

    assert result.selected == 1
    assert result.published == 0
    assert result.failed == 1
    assert message.status == "pending"
    assert message.attempt_count == 1
    assert message.next_attempt_at == now + timedelta(seconds=2)
    assert message.last_error == "queue unavailable"

    second_result = OutboxPublisher(queue).publish_pending(
        db,
        now=now + timedelta(seconds=1),
    )
    assert second_result.selected == 0


def test_outbox_publisher_ignores_already_published_messages() -> None:
    db = make_session()
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated",
        producer="strategy",
        payload={"signal_id": 13},
    )
    enqueue_outbox(db, envelope)
    queue = FakeQueue()
    now = datetime.now(timezone.utc) + timedelta(seconds=1)
    publisher = OutboxPublisher(queue)

    publisher.publish_pending(db, now=now)
    result = publisher.publish_pending(db, now=now + timedelta(seconds=1))

    assert result.selected == 0
    assert len(queue.published) == 1
