# SignalTrade Backend

FastAPI API 서버와 별도 전략 워커가 같은 PostgreSQL을 공유한다.

## 디렉토리

```text
app/
├── api/       # HTTP 인증, 사용자, 실계좌 잔고, 전략, 거래 조회
├── core/      # 환경설정과 SQLAlchemy 세션
├── models/    # PostgreSQL ORM 모델
├── schemas/   # API 요청·응답 모델
├── services/  # Upbit, 전략 계산, 주문, Telegram 로직
└── workers/   # WebSocket 전략 워커 진입점
```

## 프로세스 역할

- `backend`: 회원가입·로그인, 사용자 설정, 잔고·신호·거래 조회 API
- `strategy-worker`: Upbit 6종목 체결 WebSocket, 분봉 생성, 5종 전략 계산, 주문 분배, Telegram polling
- `db`: 전략 공식과 지원 종목을 분리하고 사용자·모드·종목·전략 조합별 설정, 신호와 주문 결과 영속화

지원 KRW 마켓은 BTC, ETH, XRP, SOL, DOGE, TRX입니다. `strategy`는 계산 공식, `supported_market`은 지원 종목, `user_strategy`는 실제 사용자 조합 설정을 저장합니다.

## 검사

프로젝트 루트에서 실행한다.

```bash
docker compose exec backend python -m pytest -q
```

## DB 변경

DB 구조는 Alembic으로 관리한다. Compose의 `migrate` 서비스가 backend보다 먼저 최신 리비전을 적용한다.

```bash
docker compose run --rm migrate
docker compose exec backend alembic current
docker compose exec backend alembic check
```

모델을 변경했을 때는 리비전을 생성하고 생성된 upgrade/downgrade 내용을 검토한다.

```bash
docker compose exec backend alembic revision --autogenerate -m "변경 설명"
docker compose exec backend alembic upgrade head
```

운영 데이터가 있는 환경에서 `docker compose down -v`를 사용하지 않는다.
