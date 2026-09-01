"""pytest 전체를 실행 중인 서비스 DB와 분리한다."""

from __future__ import annotations

import os
from pathlib import Path


# conftest는 테스트 모듈보다 먼저 import된다. 따라서 app.core.database가
# Compose/RDS DATABASE_URL을 읽기 전에 pytest 전용 DB로 항상 교체할 수 있다.
_TEST_DB_PATH = Path("/tmp/signaltrade-pytest.sqlite3")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["ENVIRONMENT"] = "test"
_TEST_DB_PATH.unlink(missing_ok=True)

import pytest

import app.models  # 모든 SQLAlchemy model을 Base.metadata에 등록한다.
from app.core.database import Base, SessionLocal, engine
from app.strategy.strategy_catalog import seed_strategy_catalog


def _reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_strategy_catalog(db)


# app.main은 import 시점에 카탈로그를 조회하므로 collection 전에 한 번 준비한다.
_reset_database()


@pytest.fixture(autouse=True)
def isolated_database() -> None:
    """각 테스트 전후에 공유 테스트 DB를 초기화한다."""
    _reset_database()
    yield
    _reset_database()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    engine.dispose()
    _TEST_DB_PATH.unlink(missing_ok=True)
