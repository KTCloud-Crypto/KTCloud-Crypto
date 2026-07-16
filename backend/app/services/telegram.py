import json
import logging
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_message(chat_id: str | None, text: str) -> None:
    """텔레그램으로 알림을 보냅니다. 토큰/chat_id 미설정 시 조용히 무시합니다."""
    if not chat_id or not settings.telegram_bot_token:
        return

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urlopen(request, timeout=5.0)
    except URLError as error:
        logger.error(f"텔레그램 알림 실패: {error}")
