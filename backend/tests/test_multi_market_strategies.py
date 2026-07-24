import uuid
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.strategy import UserStrategy
from app.models.user import User
from app.services.security import create_jwt_token, hash_password

client = TestClient(app)


def test_same_strategy_is_configured_independently_by_market() -> None:
    db = SessionLocal()
    user = User(
        username=f"multi_market_{uuid.uuid4().hex}",
        password=hash_password("test-password-123"),
        nickname="다종목테스트",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_jwt_token(
        subject=str(user.id),
        secret_key=settings.secret_key,
        expires_delta=timedelta(minutes=5),
        token_type="access",
    )
    headers = {"Authorization": f"Bearer {token}"}

    try:
        markets = client.get("/strategies/markets", headers=headers)
        assert markets.status_code == 200
        assert len(markets.json()) == 6

        eth_catalog = client.get(
            "/strategies?market=KRW-ETH",
            headers=headers,
        ).json()
        strategy = next(item for item in eth_catalog if item["code"] == "sma_cross_v1")
        response = client.put(
            f"/strategies/{strategy['id']}/subscription?market=KRW-ETH",
            headers=headers,
            json={"enabled": True, "invest_ratio": 0.2, "timeframe_minutes": 5},
        )
        assert response.status_code == 200
        assert response.json()["market"] == "KRW-ETH"
        assert response.json()["selected"] is True

        btc_catalog = client.get(
            "/strategies?market=KRW-BTC",
            headers=headers,
        )
        assert btc_catalog.status_code == 200
        btc_strategy = next(
            item for item in btc_catalog.json() if item["code"] == "sma_cross_v1"
        )
        assert btc_strategy["selected"] is False

        allocation = client.get(
            "/strategies/allocation?mode=simulated",
            headers=headers,
        ).json()
        assert allocation == {"total_ratio": 0.2, "active_count": 1}
    finally:
        db.query(UserStrategy).filter(UserStrategy.user_id == user.id).delete()
        db.query(User).filter(User.id == user.id).delete()
        db.commit()
        db.close()
