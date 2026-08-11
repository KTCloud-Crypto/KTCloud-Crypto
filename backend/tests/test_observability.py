import json
import logging

from app.core.logging import JsonFormatter, request_id_var, user_id_var


def test_json_log_contains_context_and_redacts_secrets() -> None:
    request_token = request_id_var.set("request-123")
    user_token = user_id_var.set(42)
    try:
        record = logging.LogRecord("test", logging.INFO, __file__, 1, "completed", (), None)
        record.log_type = "security"
        record.authorization = "Bearer visible-token"
        record.metadata = {"password": "visible-password", "safe": "value"}

        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(request_token)
        user_id_var.reset(user_token)

    assert payload["request_id"] == "request-123"
    assert payload["user_id"] == 42
    assert payload["authorization"] == "[REDACTED]"
    assert payload["metadata"]["password"] == "[REDACTED]"
    assert payload["metadata"]["safe"] == "value"
