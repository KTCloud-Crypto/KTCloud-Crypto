from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.strategy import Strategy, SupportedMarket, UserStrategy
from app.models.user import User
from app.strategy.subscription_control import set_subscriptions_paused


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, SupportedMarket.__table__, Strategy.__table__, UserStrategy.__table__],
    )
    return sessionmaker(bind=engine)()


def _subscriptions():
    db = _session()
    user = User(username="owner", password="hashed", nickname="owner")
    other = User(username="other", password="hashed", nickname="other")
    market = SupportedMarket(code="KRW-BTC", display_name="Bitcoin")
    strategy = Strategy(
        code="test_v1",
        name="test",
        description="test",
        timeframe_minutes=1,
        parameters={},
    )
    db.add_all([user, other, market, strategy])
    db.flush()
    first = UserStrategy(
        user_id=user.id,
        strategy_id=strategy.id,
        market_id=market.id,
        mode="simulated",
        invest_ratio=0.1,
        paused=False,
    )
    second = UserStrategy(
        user_id=user.id,
        strategy_id=strategy.id,
        market_id=market.id,
        mode="live",
        invest_ratio=0.1,
        paused=False,
    )
    other_subscription = UserStrategy(
        user_id=other.id,
        strategy_id=strategy.id,
        market_id=market.id,
        mode="simulated",
        invest_ratio=0.1,
        paused=False,
    )
    db.add_all([first, second, other_subscription])
    db.commit()
    return db, user, first, second, other_subscription


def test_single_subscription_can_be_paused_and_resumed() -> None:
    db, user, first, second, _ = _subscriptions()

    assert set_subscriptions_paused(
        db, user_id=user.id, subscription_ids=[first.id], paused=True
    ) == 1
    db.refresh(first)
    db.refresh(second)
    assert first.paused is True
    assert second.paused is False

    assert set_subscriptions_paused(
        db, user_id=user.id, subscription_ids=[first.id], paused=False
    ) == 1
    db.refresh(first)
    assert first.paused is False


def test_all_selected_subscriptions_change_without_touching_another_user() -> None:
    db, user, first, second, other = _subscriptions()

    assert set_subscriptions_paused(
        db,
        user_id=user.id,
        subscription_ids=[first.id, second.id, other.id],
        paused=True,
    ) == 2
    for subscription in (first, second, other):
        db.refresh(subscription)
    assert first.paused is True
    assert second.paused is True
    assert other.paused is False

    assert set_subscriptions_paused(
        db, user_id=user.id, subscription_ids=[first.id, second.id], paused=False
    ) == 2
    db.refresh(first)
    db.refresh(second)
    assert first.paused is False
    assert second.paused is False
