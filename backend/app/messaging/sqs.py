from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3

from app.core.config import settings
from app.messaging.envelope import MessageEnvelope


@dataclass(frozen=True)
class QueueMessage:
    receipt_handle: str
    envelope: MessageEnvelope
    receive_count: int


class SqsQueueAdapter:
    """AWS SQS와 LocalStack SQS가 공유하는 최소 Queue 인터페이스입니다."""

    def __init__(self, client: Any, queue_name: str) -> None:
        self._client = client
        self._queue_name = queue_name
        self._queue_url: str | None = None

    @classmethod
    def from_settings(cls, queue_name: str | None = None) -> "SqsQueueAdapter":
        client_options: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.sqs_endpoint_url:
            client_options["endpoint_url"] = settings.sqs_endpoint_url
        client = boto3.client("sqs", **client_options)
        return cls(client, queue_name or settings.sqs_trading_command_queue_name)

    def _get_queue_url(self) -> str:
        if self._queue_url is None:
            response = self._client.get_queue_url(QueueName=self._queue_name)
            self._queue_url = response["QueueUrl"]
        return self._queue_url

    def publish(self, envelope: MessageEnvelope, *, delay_seconds: int = 0) -> str:
        response = self._client.send_message(
            QueueUrl=self._get_queue_url(),
            MessageBody=envelope.to_json(),
            DelaySeconds=delay_seconds,
            MessageAttributes={
                "message_type": {"DataType": "String", "StringValue": envelope.message_type},
                "schema_version": {
                    "DataType": "Number",
                    "StringValue": str(envelope.schema_version),
                },
            },
        )
        return response["MessageId"]

    def receive(
        self,
        *,
        max_messages: int = 1,
        wait_time_seconds: int = 10,
        visibility_timeout: int = 30,
    ) -> list[QueueMessage]:
        response = self._client.receive_message(
            QueueUrl=self._get_queue_url(),
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time_seconds,
            VisibilityTimeout=visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        return [
            QueueMessage(
                receipt_handle=item["ReceiptHandle"],
                envelope=MessageEnvelope.from_json(item["Body"]),
                receive_count=int(item.get("Attributes", {}).get("ApproximateReceiveCount", "1")),
            )
            for item in response.get("Messages", [])
        ]

    def acknowledge(self, message: QueueMessage) -> None:
        self._client.delete_message(
            QueueUrl=self._get_queue_url(),
            ReceiptHandle=message.receipt_handle,
        )
