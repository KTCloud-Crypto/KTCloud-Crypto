from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import health
from app.identity.main import app as identity_app
from app.main import app
from app.portfolio.main import app as portfolio_app
from app.strategy.main import app as strategy_app
from app.trading.main import app as trading_app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check_queries_database() -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_all_business_api_runtimes_expose_readiness() -> None:
    for api_app in (identity_app, strategy_app, trading_app, portfolio_app):
        response = TestClient(api_app).get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    def unavailable_session():
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    monkeypatch.setattr(health, "SessionLocal", unavailable_session)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}


def test_identity_readiness_returns_503_when_redis_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(identity_app.state, "readiness_checks", [lambda: False])

    response = TestClient(identity_app).get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "dependency unavailable"}
