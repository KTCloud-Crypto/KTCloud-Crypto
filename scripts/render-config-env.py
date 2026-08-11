#!/usr/bin/env python3
"""Parameter Store JSON을 Docker Compose 전용 임시 env 파일로 변환합니다."""

import json
import sys
from pathlib import Path


REQUIRED_KEYS = {
    "ENVIRONMENT",
    "DOMAIN",
    "ALLOWED_HOSTS",
    "CORS_ORIGINS",
}
OPTIONAL_KEYS = {
    "HTTPS_ENABLED",
    "LIVE_TRADING_ENABLED",
    "POSITION_RECONCILIATION_SECONDS",
    "STALE_EXECUTION_SECONDS",
    "STRATEGY_REFRESH_SECONDS",
    "TELEGRAM_BOT_USERNAME",
    "UPBIT_API_BASE_URL",
    "UPBIT_WS_URL",
    "WATCH_MARKETS",
}


def render(source_path: Path, output_path: Path) -> None:
    source = sys.stdin if str(source_path) == "-" else source_path.open(encoding="utf-8")
    try:
        config = json.load(source)
    finally:
        if source is not sys.stdin:
            source.close()

    if not isinstance(config, dict):
        raise SystemExit("Parameter Store value must be a JSON object")

    unknown = set(config) - REQUIRED_KEYS - OPTIONAL_KEYS
    missing = REQUIRED_KEYS - set(config)
    if unknown:
        raise SystemExit(f"Unsupported Parameter Store keys: {', '.join(sorted(unknown))}")
    if missing:
        raise SystemExit(f"Missing Parameter Store keys: {', '.join(sorted(missing))}")

    for key, value in config.items():
        if not isinstance(value, str):
            raise SystemExit(f"Parameter Store value must be a string: {key}")
        if key in REQUIRED_KEYS and not value:
            raise SystemExit(f"Parameter Store value must not be empty: {key}")
        if any(character in value for character in "\r\n\0"):
            raise SystemExit(f"Parameter Store value must be one line: {key}")

    output = sys.stdout if str(output_path) == "-" else output_path.open("w", encoding="utf-8")
    try:
        for key in sorted(config):
            # Compose env 파일의 double-quoted 값을 안전하게 생성하고 '$' 재확장을 막습니다.
            encoded = json.dumps(config[key].replace("$", "$$"), ensure_ascii=True)
            output.write(f"{key}={encoded}\n")
    finally:
        if output is not sys.stdout:
            output.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: render-config-env.py SOURCE_JSON|- OUTPUT_ENV|-")
    render(Path(sys.argv[1]), Path(sys.argv[2]))
