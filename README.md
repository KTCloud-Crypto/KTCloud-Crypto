# SignalTrade

SignalTrade는 Upbit REST API와 WebSocket 실시간 체결 데이터를 이용해 사용자별 전략을 계산하고, 모의투자 또는 실전 주문을 실행하는 자동매매 웹 서비스입니다. API 서버와 자동매매 Worker를 분리해 웹 요청과 백그라운드 거래 작업을 독립적으로 운영하며, 로그·메트릭 기반 관측성과 태그 기반 운영 배포를 함께 구성합니다.

## 주요 기능

### 계정 및 보안

- JWT Access Token 기반 인증
- 로그인 5회 실패 시 계정 임시 잠금과 Telegram 안내
- Telegram 일회용 코드를 이용한 비밀번호 재설정
- Upbit API Key 유효성 검증 및 Fernet 암호화 저장
- 로그인, 로그아웃, 계정 및 민감 설정 변경에 대한 보안 감사 로그
- 요청 ID, 사용자 ID, 클라이언트 IP를 포함한 구조화 로그
- 비밀번호·Token·API Key 등 민감 필드 자동 마스킹

### 자동매매

- 모의투자와 실전투자 상태 및 실행 내역 분리
- Upbit WebSocket 체결 데이터를 이용한 분봉 생성과 전략 평가
- 종목·전략 조합별 활성화, 투자 비율 및 실행 주기 관리
- 미체결 주문 상태 확인, 실제 잔고 불일치 감지, 중단 주문 복구
- 전략별 포지션과 할당 금액 관리
- Telegram 연동, 알림, 잔고 동기화 및 명령 처리
- 실현손익, 승률, 자산과 종목별 거래 분석

### 마켓 및 전략 카탈로그

서비스에 노출되는 마켓과 전략은 Backend의 카탈로그 정의와 데이터베이스의 활성 상태를 기준으로 관리합니다. Worker는 활성화된 종목·전략 조합만 주기적으로 불러와 계산하며, 사용자는 화면에서 제공되는 항목 중 실행 모드와 투자 비율을 설정합니다.

`미배정 자산`은 Upbit에는 존재하지만 자동매매 전략에 할당하지 않은 실전 자산을 표현하는 내부 항목이며, 자동 주문을 실행하지 않습니다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React 19, Vite 7, React Router, Nginx |
| Backend | Python, FastAPI, Uvicorn, SQLAlchemy 2, Alembic |
| Worker | asyncio, Upbit REST API/WebSocket, Telegram Bot API |
| Database | PostgreSQL 15 |
| Container | Docker, Docker Compose |
| Observability | Prometheus, Grafana, Loki, Grafana Alloy, node-exporter, cAdvisor, postgres-exporter |
| CI/CD | GitHub Actions, Amazon ECR, AWS Systems Manager Run Command |
| Secrets | AWS Secrets Manager, SSM Parameter Store SecureString |
| Runtime | AWS EC2, Nginx, Let's Encrypt |

## 전체 구성

```text
사용자 브라우저
      │ HTTPS
      ▼
Nginx + React
      │ /api
      ▼
FastAPI Backend ───────────── PostgreSQL
      ▲                           ▲
      │                           │
      └──────── strategy-worker ──┘
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
      Upbit REST  Upbit WS  Telegram

Backend / Worker stdout ── Docker local log ── Alloy ── Loki ──┐
Backend / Worker /metrics ──────────────── Prometheus ──────────┤
Host / Container / PostgreSQL exporters ─ Prometheus ──────────┤
                                                               ▼
                                                             Grafana
```

### 애플리케이션 컨테이너

| 서비스 | 역할 |
|---|---|
| `frontend` | React 정적 파일 제공, `/api`와 `/monitoring` 리버스 프록시, TLS 처리 |
| `backend` | 인증, 사용자 설정, 전략·포지션·거래·분석 API 제공 |
| `strategy-worker` | 시세 수신, 전략 계산, 주문 실행, Telegram polling, 정합성 점검과 복구 |
| `migrate` | Backend 시작 전에 `alembic upgrade head` 실행 후 종료 |
| `db` | 사용자·전략·주문·거래·보안 감사 데이터 저장 |

`backend`, `strategy-worker`, `migrate`는 같은 Backend 이미지를 사용하지만 실행 명령과 수명 주기가 다릅니다.

### 모니터링 컨테이너

| 서비스 | 역할 |
|---|---|
| `grafana` | 로그와 메트릭 대시보드 제공 |
| `prometheus` | 애플리케이션 및 인프라 메트릭 수집·저장 |
| `loki` | JSON 구조화 로그 저장·검색 |
| `alloy` | Docker stdout 로그를 수집해 Loki로 전송 |
| `node-exporter` | 호스트 CPU·메모리·디스크 메트릭 제공 |
| `cadvisor` | 컨테이너 CPU·메모리 메트릭 제공 |
| `postgres-exporter` | PostgreSQL 상태와 통계 메트릭 제공 |

## 저장 위치

| 데이터 | 저장 위치 |
|---|---|
| PostgreSQL 데이터 | `postgres_data` Docker 볼륨 |
| 컨테이너 1차 로그 | Docker `local` logging driver 영역 |
| Loki 조회용 로그 | `monitoring_loki_data` Docker 볼륨 |
| Prometheus 메트릭 | `monitoring_prometheus_data` Docker 볼륨 |
| Grafana 설정 | `monitoring_grafana_data` Docker 볼륨 |

Backend와 Worker 로그는 컨테이너당 최대 10MB 파일 5개로 회전합니다. `docker compose down`은 볼륨을 유지하지만 `docker compose down -v`는 데이터를 삭제하므로 운영 환경에서 사용하지 않습니다.

## 로컬 실행

### 사전 요구 사항

- Docker Engine 또는 Docker Desktop
- Docker Compose v2
- Upbit API Key와 Telegram Bot Token은 선택 사항

### 1. 환경 파일 준비

```bash
cp .env.example .env
cp monitoring/.env.example monitoring/.env
```

최소한 다음 값을 안전한 값으로 변경합니다.

```env
# .env
POSTGRES_PASSWORD=
DATABASE_URL=postgresql://postgres:동일한비밀번호@db:5432/fastapi_db
SECRET_KEY=
MASTER_ENCRYPTION_KEY=

# monitoring/.env
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=
POSTGRES_EXPORTER_DSN=postgresql://monitoring:비밀번호@db:5432/fastapi_db?sslmode=disable
```

암호화 키 생성 예시:

```bash
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

PostgreSQL exporter는 애플리케이션 계정 대신 읽기 전용 모니터링 계정을 사용하는 것을 권장합니다. 자세한 생성 방법은 [로그 및 모니터링 운영 문서](docs/OBSERVABILITY.md#postgresql-exporter-계정)를 참고하세요.

### 2. 로컬 모니터링 Basic Auth 파일 준비

Frontend의 `/monitoring/` 경로는 Nginx Basic Auth를 사용합니다. 로컬 테스트용 계정은 다음과 같이 생성할 수 있습니다.

```bash
docker run --rm httpd:2.4-alpine htpasswd -nbB local-monitor '로컬에서만-사용할-비밀번호' > monitoring/.htpasswd
```

### 3. 모니터링 시작

애플리케이션 Compose가 외부 네트워크 `signaltrade-observability`를 사용하므로 모니터링을 먼저 시작합니다.

```bash
docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  up -d
```

### 4. 애플리케이션 시작

```bash
docker compose up -d --build
docker compose ps
```

### 5. 접속

| 대상 | 주소 |
|---|---|
| Web UI | <http://localhost> |
| Backend health | <http://localhost:8000/health> |
| Swagger UI | <http://localhost:8000/docs> |
| Grafana 직접 접속 | <http://localhost:3000> |
| Nginx를 통한 Grafana | <http://localhost/monitoring/> |

운영 환경에서는 Swagger, ReDoc, OpenAPI 문서를 비활성화하고 `/metrics`를 외부 프록시로 공개하지 않습니다.

## 화면 구성

```text
로그인 / 회원가입 / 비밀번호 재설정
  └── 통합 홈
      ├── 모의투자
      │   ├── 전략 설정과 투자금 배분
      │   ├── 모의계좌·포지션
      │   └── 신호·실행·거래 내역
      ├── 실전투자
      │   ├── Upbit API Key와 실전투자 활성화
      │   ├── 전략 설정과 자산 배분
      │   ├── 실제 잔고·포지션·정합성 조정
      │   └── 신호·주문·거래 내역
      ├── 사용자 분석
      │   ├── 기간별 실현손익과 승률
      │   └── 종목별 거래 비중과 손익
      ├── 가이드
      │   ├── 서비스 이용
      │   ├── 전략 안내
      │   └── Upbit API Key 발급
      └── 계정 설정
          ├── 닉네임·비밀번호 변경
          ├── Telegram 연결
          └── Upbit API Key 등록·교체·해제
```

## Telegram

`.env`에 BotFather가 발급한 값을 설정합니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
```

웹 설정 화면에서 1회용 연동 코드를 발급한 뒤 Bot 채팅에 전송합니다.

```text
/start 123456
```

주요 명령 예시:

```text
/status
/balance
/positions
/close
```

## 로그 및 메트릭

### 로그 흐름

```text
애플리케이션 JSON stdout
  → Docker local logging driver
  → Grafana Alloy
  → Loki
  → Grafana
```

구조화 요청 로그의 주요 필드:

```json
{
  "timestamp": "2026-08-13T07:27:29+00:00",
  "level": "INFO",
  "log_type": "operation",
  "service": "backend",
  "environment": "production",
  "event": "http_request_completed",
  "request_id": "...",
  "user_id": 1,
  "method": "GET",
  "route": "/strategies/{strategy_id}",
  "status_code": 200,
  "duration_ms": 31.42,
  "client_ip": "..."
}
```

### 주요 메트릭

- API 요청량, 상태 코드, 처리 중 요청 수와 p95 응답시간
- Upbit API 작업별 성공·실패와 p95 응답시간
- DB 쿼리 종류별 p95 처리시간
- Worker 작업 실행 상태, 성공·실패, 처리시간과 마지막 성공 시각
- Upbit WebSocket 연결과 마지막 시세 수신 시각
- 전략 신호, 주문 결과, 포지션 불일치와 복구 횟수
- PostgreSQL, 호스트, 컨테이너 자원 사용량
- Alloy → Loki 전송량과 로그 유실량

DB 계측은 `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `OTHER` 작업 종류와 처리시간만 기록하며 쿼리 원문과 파라미터를 수집하지 않습니다. 2초 이상 느린 HTTP 요청은 `request_id`, `route`, `duration_ms`로 Upbit·DB 지표와 함께 추적합니다.

### Grafana 대시보드

| 대시보드 | 용도 |
|---|---|
| `SignalTrade 메인 요약` | 서비스 상태, 사용자 영향, Worker, 인프라와 오류 로그 요약 |
| `SignalTrade 서비스 개요` | Backend와 Worker 상세 상태 및 작업 신선도 |
| `SignalTrade API 트래픽` | 경로별 트래픽, 오류, Upbit·DB 지연 원인 분석 |
| `SignalTrade PostgreSQL 모니터링` | 연결, 트랜잭션, 교착, 용량과 캐시 적중률 |
| `SignalTrade 운영 모니터링` | Nginx 오류, 로그 파이프라인, 호스트·컨테이너 자원 |

각 패널의 정보 아이콘은 측정 대상, 정상 범위, 데이터가 없을 때의 의미와 문제 확인 위치를 안내합니다.

## 테스트와 개발 검사

```bash
# Backend 전체 테스트
docker compose exec backend python -m pytest -q

# DB 모델과 마이그레이션 비교
docker compose exec backend alembic check

# Frontend lint 및 production build
docker compose exec frontend npm run lint
docker compose exec frontend npm run build

# 전체 이미지 빌드
docker compose build
```

GitHub Actions의 CI Gate는 변경 경로에 따라 필요한 작업만 실행합니다.

- Backend: PostgreSQL 서비스 시작, 마이그레이션, `alembic check`, pytest, Docker build
- Frontend: `npm ci`, ESLint, Vite production build, Docker build
- `develop` push와 `develop`·`main` 대상 PR 검사
- `main` 대상 PR은 `develop` 브랜치에서만 허용

## 운영 배포

운영 배포는 `main`에 포함된 `vMAJOR.MINOR.PATCH` 태그 push로 시작합니다.

```text
release tag
  → Backend / Frontend CI
  → Docker Buildx
  → Amazon ECR에 태그·Git SHA 이미지 push
  → 이미지 digest 고정
  → AWS OIDC 임시 자격 증명
  → SSM Run Command로 EC2 배포
  → DB 백업
  → Alembic migration
  → health check
  → 실패 시 이전 이미지로 자동 rollback
```

운영 설정은 목적에 따라 분리합니다.

- AWS Secrets Manager: DB 비밀번호, JWT Secret, API Key 암호화 키 등 비밀값
- SSM Parameter Store: 일반 애플리케이션 설정 JSON
- SSM SecureString: Grafana 관리자 계정, PostgreSQL exporter DSN, Nginx Basic Auth bcrypt 항목
- GitHub Environment variables: AWS 리전, ECR 저장소, EC2 인스턴스, 배포 경로 등 식별값

운영 Grafana는 `https://signaltrade.cloud/monitoring/`에서 Nginx Basic Auth와 Grafana 로그인으로 이중 보호하며, 3000 포트는 `127.0.0.1`에만 바인딩합니다. 자세한 구성은 [CD 설정 문서](docs/CD_SETUP.md)와 [관측성 운영 문서](docs/OBSERVABILITY.md)를 참고하세요.

## 자주 사용하는 명령

```bash
# 애플리케이션 상태
docker compose ps

# 애플리케이션 전체 로그
docker compose logs -f

# Backend / Worker 로그
docker compose logs -f backend strategy-worker

# PostgreSQL 접속
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

# 모니터링 상태
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml ps

# Grafana / Prometheus / Loki 로그
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml \
  logs -f grafana prometheus loki

# 애플리케이션 중지(볼륨 유지)
docker compose down

# 모니터링 중지(볼륨 유지)
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml down

# 모니터링 시작 후 애플리케이션 재빌드
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml up -d
docker compose up -d --build
```

## 프로젝트 구조

```text
KTCloud-Crypto/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI router
│   │   ├── core/         # 설정, DB, 로그, 메트릭
│   │   ├── models/       # SQLAlchemy model
│   │   ├── schemas/      # Pydantic schema
│   │   ├── services/     # 거래·전략·보안 도메인 로직
│   │   └── workers/      # 비동기 Worker runtime
│   ├── alembic/          # DB migration
│   └── tests/            # Backend test
├── frontend/
│   └── src/
│       ├── components/   # 공통·대시보드 컴포넌트
│       ├── pages/        # 화면 단위 컴포넌트
│       ├── hooks/        # polling 등 공통 hook
│       └── api/          # Backend API client
├── monitoring/
│   ├── alloy/            # Docker 로그 수집
│   ├── grafana/          # datasource와 dashboard provisioning
│   ├── loki/             # 로그 저장·보존 설정
│   └── prometheus/       # scrape target 설정
├── scripts/              # 운영 배포와 설정 렌더링
├── docs/                 # 구조·운영·배포 문서
├── docker-compose.yml
└── docker-compose.production.yml
```

## 문서

- [설치 및 실행 방법](SETUP.md)
- [프로젝트 구조와 데이터 흐름](docs/ARCHITECTURE_AND_USAGE.md)
- [로그 및 모니터링 운영](docs/OBSERVABILITY.md)
- [CI/CD 및 AWS 운영 배포](docs/CD_SETUP.md)
- [현재 구현 및 병합 상태](docs/CURRENT_IMPLEMENTATION.md)
- [MVP 안정화 및 다종목 확장 기록](docs/MVP_STABILIZATION.md)
- [Backend 구조](backend/README.md)
- [Frontend 구조](frontend/README.md)

## 주의 사항

자동매매와 실전 주문은 자산 손실 위험이 있습니다. API Key는 출금 권한 없이 필요한 최소 권한만 부여하고, 충분한 모의투자 검증 후 사용자별 실전투자 설정을 활성화하세요. 이 프로젝트의 전략과 결과는 수익을 보장하지 않습니다.
