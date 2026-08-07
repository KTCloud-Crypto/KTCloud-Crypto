#!/usr/bin/env python3
"""Secrets Manager JSON을 Docker Compose 전용 임시 env 파일로 변환합니다."""

import json
import sys
from pathlib import Path
from urllib.parse import quote


REQUIRED_KEYS = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "SECRET_KEY",
    "MASTER_ENCRYPTION_KEY",
}
OPTIONAL_KEYS = {"TELEGRAM_BOT_TOKEN"}


def render(source_path: Path, output_path: Path) -> None:
    source = sys.stdin if str(source_path) == "-" else source_path.open(encoding="utf-8")
    try:
        secret = json.load(source)
    finally:
        if source is not sys.stdin:
            source.close()
    if not isinstance(secret, dict):
        raise SystemExit("Secrets Manager SecretString must be a JSON object")

    unknown = set(secret) - REQUIRED_KEYS - OPTIONAL_KEYS
    missing = REQUIRED_KEYS - set(secret)
    if unknown:
        raise SystemExit(f"Unsupported Secrets Manager keys: {', '.join(sorted(unknown))}")
    if missing:
        raise SystemExit(f"Missing Secrets Manager keys: {', '.join(sorted(missing))}")

    for key, value in secret.items():
        if not isinstance(value, str):
            raise SystemExit(f"Secrets Manager value must be a string: {key}")
        if key in REQUIRED_KEYS and not value:
            raise SystemExit(f"Secrets Manager value must not be empty: {key}")
        if any(character in value for character in "\r\n\0"):
            raise SystemExit(f"Secrets Manager value must be one line: {key}")

    database_url = "postgresql://{}:{}@db:5432/{}".format(
        quote(secret["POSTGRES_USER"], safe=""),
        quote(secret["POSTGRES_PASSWORD"], safe=""),
        quote(secret["POSTGRES_DB"], safe=""),
    )
    values = {**secret, "DATABASE_URL": database_url}

    output = sys.stdout if str(output_path) == "-" else output_path.open("w", encoding="utf-8")
    try:
        for key in sorted(values):
            # Compose가 '$NAME'을 다시 환경변수로 해석하지 않도록 '$$'로 이스케이프합니다.
            encoded = json.dumps(values[key].replace("$", "$$"), ensure_ascii=True)
            output.write(f"{key}={encoded}\n")
    finally:
        if output is not sys.stdout:
            output.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: render-secrets-env.py SOURCE_JSON|- OUTPUT_ENV|-")
    render(Path(sys.argv[1]), Path(sys.argv[2]))
