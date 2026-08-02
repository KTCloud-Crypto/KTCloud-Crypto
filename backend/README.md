# SignalTrade Backend

FastAPI API 서버와 별도 전략 워커가 같은 PostgreSQL을 공유한다.

## 디렉토리

```text
app/
├── api/       # HTTP API
├── core/      # 설정과 DB 세션
├── models/    # ORM 모델
├── schemas/   # 요청·응답 모델
├── services/  # 전략, 주문, Telegram 로직
└── workers/   # 워커 진입점
```

## 프로세스 역할

- `backend`: 인증, 사용자 설정, 잔고·신호·거래 조회 API
- `migrate`: `backend`보다 먼저 DB 스키마를 적용하는 일회성 컨테이너
- `strategy-worker`: 체결 수신, 분봉 생성, 전략 계산, 주문 분배, Telegram polling
- `db`: 전략, 종목, 사용자 설정, 신호, 주문 결과 저장

종목은 `supported_market`, 전략은 `strategy`, 사용자 조합은 `user_strategy`에 저장합니다.

## 검사

프로젝트 루트에서 실행한다.

```bash
docker compose exec backend python -m pytest -q
```

## DB 변경

DB 구조는 Alembic으로 관리한다. Compose의 `migrate` 서비스가 먼저 최신 리비전을 적용한 뒤 종료된다.

```bash
docker compose run --rm migrate
docker compose exec backend alembic current
docker compose exec backend alembic check
```

모델을 변경했을 때는 리비전을 생성하고 upgrade/downgrade를 검토한다.

```bash
docker compose exec backend alembic revision --autogenerate -m "변경 설명"
docker compose exec backend alembic upgrade head
```

운영 데이터가 있는 환경에서 `docker compose down -v`를 사용하지 않는다.
