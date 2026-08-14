# SignalTrade Backend

FastAPI API 서버와 `strategy-worker`가 같은 코드베이스를 공유합니다. API 서버는 사용자 요청을 처리하고, Worker는 시세 수신·전략 계산·주문 후속 처리·Telegram 연동을 백그라운드에서 수행합니다.

## 실행 프로세스

| 프로세스 | 명령 | 역할 |
|---|---|---|
| Backend | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | HTTP API, health, Prometheus 메트릭 |
| Worker | `python -m app.workers.runtime` | 실시간 시세, 전략 실행, 주문 정합성, 복구 |
| Migration | `alembic upgrade head` | 애플리케이션 시작 전 DB 스키마 갱신 |

운영에서는 API 문서가 비활성화됩니다. 로컬에서만 `/docs`, `/redoc`, `/openapi.json`을 사용할 수 있습니다.

## 디렉터리

```text
backend/
├── app/
│   ├── api/          # FastAPI 라우터
│   ├── core/         # 설정, DB, 보안, 로깅, 메트릭
│   ├── models/       # SQLAlchemy 모델
│   ├── schemas/      # 요청·응답 스키마
│   ├── services/     # 전략, 주문, Upbit, Telegram 도메인 로직
│   └── workers/      # Worker 실행 진입점과 주기 작업
├── alembic/          # Alembic revision
├── tests/            # pytest 테스트
├── alembic.ini
└── requirements.txt
```

## API 영역

| Prefix | 역할 |
|---|---|
| `/auth` | 회원가입, 로그인, 비밀번호 재설정 |
| `/users` | 사용자 정보, API Key, Telegram, 계정 설정 |
| `/strategies` | 전략 카탈로그, 사용자 설정, 실행·주문 조회 |
| `/positions` | 잔고, 포지션, 정합성 확인과 조정 |
| `/paper-account` | 모의계좌와 원장 |
| `/trades` | 거래 기록 |
| `/analytics` | 손익·승률·거래 분석 |
| `/health` | 서비스 상태 확인 |
| `/metrics` | Prometheus 수집용 메트릭; 외부 공개 금지 |

전체 경로와 요청 형식은 개발 환경의 Swagger UI 또는 `app/api/`를 기준으로 확인합니다.

## 데이터와 실행 원칙

- 마켓·전략 목록은 카탈로그 정의와 DB 활성 상태로 관리합니다. 문서에 개수를 고정하지 않습니다.
- 사용자 전략은 투자 모드·마켓·전략 조합별로 저장합니다.
- 실전 포지션은 주문·체결 기록을 기준으로 계산하며, Upbit 잔고와 차이가 나면 정합성 작업으로 조정합니다.
- API와 Worker가 동시에 스키마를 변경하지 않도록 마이그레이션 컨테이너가 먼저 실행됩니다.
- Upbit API Key는 암호화해 저장하고 로그에는 비밀번호, Token, API Key를 기록하지 않습니다.

## Worker 관측 항목

Worker는 작업 실행 수, 성공·실패 결과, 처리시간, 마지막 성공 시각을 노출합니다. 주요 주기 작업은 주문 상태 확인, 포지션 불일치 검사, 중단 주문 복구이며 각 작업의 정상 주기가 다르므로 Grafana 임계값도 작업별로 구분합니다.

API와 Worker는 한 줄 JSON을 stdout에 출력합니다. 요청 완료 로그에는 가능한 경우 `request_id`, `user_id`, `method`, `route`, `status_code`, `duration_ms`, `client_ip`가 포함됩니다.

## 로컬 개발

프로젝트 루트에서 실행합니다.

```bash
docker compose up -d --build
docker compose exec backend python -m pytest -q
docker compose exec backend alembic current
docker compose logs -f backend strategy-worker
```

호스트에서 직접 실행할 경우 먼저 `.env`와 PostgreSQL을 준비한 뒤 실행합니다.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

자세한 전체 실행 순서는 [../SETUP.md](../SETUP.md), 데이터 흐름은 [../docs/ARCHITECTURE_AND_USAGE.md](../docs/ARCHITECTURE_AND_USAGE.md)를 참고합니다.
