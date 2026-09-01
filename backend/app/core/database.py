import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.core.metrics import DATABASE_QUERY_DURATION

# SQLite는 pytest의 격리 DB로만 사용합니다. TestClient가 별도 스레드에서
# 의존성 세션을 열 수 있도록 해당 경우에만 SQLite의 스레드 제한을 해제합니다.
_engine_options = (
    {"connect_args": {"check_same_thread": False}}
    if settings.database_url.startswith("sqlite")
    else {}
)
engine = create_engine(settings.database_url, **_engine_options)


def _query_operation(statement: str) -> str:
    """쿼리 원문을 노출하지 않고 낮은 카디널리티의 작업 종류만 반환합니다."""
    operation = statement.lstrip().split(None, 1)[0].upper() if statement.strip() else "OTHER"
    return operation if operation in {"SELECT", "INSERT", "UPDATE", "DELETE"} else "OTHER"


@event.listens_for(engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_started_at", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    started_at = conn.info.get("query_started_at", []).pop()
    DATABASE_QUERY_DURATION.labels(_query_operation(statement)).observe(
        time.perf_counter() - started_at
    )


@event.listens_for(engine, "handle_error")
def _handle_query_error(exception_context):
    connection = exception_context.connection
    if connection is None:
        return
    started = connection.info.get("query_started_at", [])
    if started:
        DATABASE_QUERY_DURATION.labels(
            _query_operation(exception_context.statement or "")
        ).observe(time.perf_counter() - started.pop())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """요청마다 DB 세션을 열고 응답이 끝나면 반드시 닫습니다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
