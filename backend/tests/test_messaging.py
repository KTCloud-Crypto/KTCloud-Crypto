from datetime import datetime

import pytest
from pydantic import ValidationError

from app.messaging.envelope import MessageEnvelope
from app.messaging.sqs import SqsQueueAdapter


class FakeSqsClient:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.deleted: list[dict] = []
        self.received: list[dict] = []

    def get_queue_url(self, **kwargs):
        return {"QueueUrl": f"http://queue/{kwargs['QueueName']}"}

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "sqs-message-1"}

    def receive_message(self, **kwargs):
        self.received.append(kwargs)
        return {
            "Messages": [
                {
                    "ReceiptHandle": "receipt-1",
                    "Body": self.sent[0]["MessageBody"],
                    "Attributes": {"ApproximateReceiveCount": "2"},
                }
            ]
        }

    def delete_message(self, **kwargs):
        self.deleted.append(kwargs)


def test_message_envelope_round_trip() -> None:
    envelope = MessageEnvelope.create(
        message_type="ExecuteStrategySignal",
        producer="strategy",
        correlation_id="request-123",
        idempotency_key="signal:1:strategy:2:buy",
        payload={"signal_id": 1, "side": "buy"},
    )

    restored = MessageEnvelope.from_json(envelope.to_json())

    assert restored == envelope
    assert restored.occurred_at.utcoffset().total_seconds() == 0


def test_message_envelope_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        MessageEnvelope(
            message_type="TradeExecuted",
            occurred_at=datetime(2026, 8, 26, 10, 0, 0),
            correlation_id="request-123",
            producer="trading",
            payload={},
        )


def test_sqs_adapter_publish_receive_and_acknowledge() -> None:
    client = FakeSqsClient()
    adapter = SqsQueueAdapter(client, "trading-commands")
    envelope = MessageEnvelope.create(
        message_type="ExecuteStrategySignal",
        producer="strategy",
        payload={"signal_id": 10},
    )

    message_id = adapter.publish(envelope)
    received = adapter.receive(visibility_timeout=300)[0]
    adapter.acknowledge(received)

    assert message_id == "sqs-message-1"
    assert received.envelope == envelope
    assert received.receive_count == 2
    assert client.received[0]["VisibilityTimeout"] == 300
    assert client.deleted == [
        {"QueueUrl": "http://queue/trading-commands", "ReceiptHandle": "receipt-1"}
    ]
