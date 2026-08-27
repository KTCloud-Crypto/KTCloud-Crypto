import json
import logging
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_message(chat_id: Optional[str], text: str) -> bool:
    """텔레그램으로 알림을 보냅니다. 토큰/chat_id 미설정 시 조용히 무시합니다."""
    if not chat_id or not settings.telegram_bot_token:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5.0):
            return True
    except URLError as error:
        # 예외 문자열에 봇 토큰이 포함된 URL이 들어갈 수 있어 타입만 기록합니다.
        logger.error("Telegram notification failed: %s", type(error).__name__)
        return False
