# SignalTrade 설치 및 실행

이 문서는 Docker Compose를 사용해 SignalTrade를 로컬 또는 Ubuntu/EC2에서 실행하는 방법을 설명합니다.

## 1. 사전 준비

필요한 프로그램:

- Git
- Docker Engine 또는 Docker Desktop
- Docker Compose v2

버전 확인:

```bash
git --version
docker --version
docker compose version
```

## 2. 코드 준비

### 처음 받는 경우

```bash
git clone https://github.com/KTCloud-Crypto/KTCloud-Crypto.git
cd KTCloud-Crypto
```

### 이미 받은 경우

작업 중인 파일이 없는지 먼저 확인합니다.

```bash
git status -sb
git fetch origin develop
git switch develop
git pull --ff-only origin develop
```

## 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env`의 주요 항목:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=안전한_DB_비밀번호
POSTGRES_DB=fastapi_db
DATABASE_URL=postgresql://postgres:안전한_DB_비밀번호@db:5432/fastapi_db

SECRET_KEY=JWT_서명용_긴_랜덤_문자열
MASTER_ENCRYPTION_KEY=Fernet_키

UPBIT_API_BASE_URL=https://api.upbit.com
UPBIT_WS_URL=wss://api.upbit.com/websocket/v1
WATCH_MARKETS=KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-DOGE,KRW-TRX

LIVE_TRADING_ENABLED=false
ENVIRONMENT=development

TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=

STRATEGY_REFRESH_SECONDS=30
POSITION_RECONCILIATION_SECONDS=60
STALE_EXECUTION_SECONDS=120

VITE_API_BASE_URL=http://localhost:8000
```

### `SECRET_KEY`

JWT 인증 토큰 서명에 사용합니다. 충분히 긴 랜덤 문자열을 사용하고 Git에 올리지 않습니다.

예시 생성:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### `MASTER_ENCRYPTION_KEY`

사용자의 Upbit Access Key와 Secret Key를 각각 암호화·복호화하는 서버 키입니다.

```bash
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

주의사항:

- API Key 두 개를 합친 값이 아닙니다.
- DB가 유지되는 동안 동일한 키를 안전하게 보관해야 합니다.
- 이 키를 변경하면 기존 암호문을 복호화할 수 없습니다.
- Git에 커밋하지 않습니다.
- 운영 환경에서는 AWS Secrets Manager 또는 SSM Parameter Store 사용을 권장합니다.

### Telegram

알림 기능을 사용할 경우 BotFather가 발급한 값을 입력합니다.

```env
TELEGRAM_BOT_TOKEN=123456:토큰
TELEGRAM_BOT_USERNAME=생성한봇이름_bot
```

비워두면 Telegram 기능만 비활성화되고 나머지 서비스는 실행됩니다.

### 실제 주문 설정

초기 실행에서는 반드시 다음 값을 권장합니다.

```env
LIVE_TRADING_ENABLED=false
```

`true`이면 실전 모드를 사용하는 계정의 자연 전략 신호 및 실전 테스트 신호가 실제 Upbit 주문으로 이어질 수 있습니다.

## 4. 로컬 실행

```bash
docker compose up --build -d
docker compose ps
```

정상 상태:

```text
backend          Up (healthy)
db               Up (healthy)
frontend         Up
strategy-worker  Up
```

상태 확인:

```bash
curl http://localhost:8000/health
docker compose logs --tail=50 backend
docker compose logs --tail=50 strategy-worker
```

브라우저:

```text
http://localhost
```

API는 로컬에서 `http://localhost:8000`으로도 직접 확인할 수 있습니다.

## 5. 첫 사용 순서

1. Upbit에서 API Key를 발급합니다.
2. Upbit API Key에 필요한 조회·주문 권한과 서버 공인 IP를 설정합니다.
3. SignalTrade 회원가입 화면에서 사용자 정보와 Upbit Key를 등록합니다.
4. 로그인 후 통합 홈에서 Upbit API와 Telegram 상태를 확인합니다.
5. 모의투자에서 투자금을 설정하고 전략을 선택합니다.
6. 분봉, 투자 비율, 손절률, 목표 수익률을 저장합니다.
7. 모의 매수·매도와 포지션 및 Telegram 알림을 검증합니다.
8. 실전투자 사용 전 `.env`의 `LIVE_TRADING_ENABLED` 상태를 확인합니다.

## 6. Telegram 연결

1. 통합 홈에서 모의투자 또는 실전투자 관리로 들어갑니다.
2. Telegram 영역에서 연동 코드를 발급합니다.
3. 봇 채팅에 다음 형식으로 전송합니다.

```text
/start 123456
```

실제 Upbit 잔고와 전략 기록 비교:

```text
/sync
```

## 7. DB 확인

테이블 확인:

```bash
docker compose exec db psql -U postgres -d fastapi_db -c '\dt'
```

DB 접속:

```bash
docker compose exec db psql -U postgres -d fastapi_db
```

psql 안에서 자주 쓰는 명령:

```text
\dt                    테이블 목록
\d supported_market    지원 종목 구조
\d user_strategy       테이블 구조
SELECT * FROM "user";   사용자 조회
SELECT * FROM supported_market ORDER BY sort_order; 지원 종목 조회
\q                     psql 종료
```

DB 데이터는 Docker volume `postgres_data`에 저장됩니다.

```bash
docker volume ls
docker volume inspect ktcloud-crypto_postgres_data
```

## 8. DB 마이그레이션

DB 구조는 Alembic으로 관리합니다. `docker compose up`을 실행하면 `migrate` 서비스가 backend보다 먼저 `alembic upgrade head`를 실행합니다.

```bash
docker compose run --rm migrate
docker compose exec backend alembic current
docker compose exec backend alembic check
```

SQLAlchemy 모델을 변경했을 때는 다음 리비전을 생성합니다.

```bash
docker compose exec backend alembic revision --autogenerate -m "변경 설명"
docker compose exec backend alembic upgrade head
```

자동 생성된 리비전도 바로 적용하지 말고 upgrade와 downgrade 내용을 검토해야 합니다. 운영 DB 변경 전에는 백업을 권장합니다.

### Alembic 도입 이전 로컬 DB

Alembic 적용 전에 `Base.metadata.create_all()`로 만든 DB에는 기존 테이블이 있지만 `alembic_version`이 없습니다. 이 DB에 초기 마이그레이션을 바로 실행하면 `relation "user" already exists` 오류가 발생합니다. 데이터를 임의로 삭제하거나 초기 리비전을 바로 stamp하지 말고 먼저 백업 후 기존 스키마와 초기 리비전을 비교해야 합니다.

기존 볼륨을 보존하면서 최신 코드를 별도 로컬 환경에서 확인하려면 다른 Compose 프로젝트 이름을 사용합니다.

```bash
docker compose -p ktcloud-crypto-develop up -d --build
docker compose -p ktcloud-crypto-develop ps
```

이 명령은 `ktcloud-crypto-develop_postgres_data`라는 별도 DB 볼륨을 사용합니다. 따라서 이전 로컬 계정과 거래 데이터는 새 환경에 나타나지 않습니다.

## 9. 테스트

```bash
# backend 전체 테스트
docker compose exec backend python -m pytest -q

# frontend 정적 검사
docker compose exec frontend npm run lint

# frontend production build
docker compose exec frontend npm run build

# Docker 이미지 build
docker compose build
```

## 10. Ubuntu/EC2 실행

### Docker 설치

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

그룹 반영을 위해 SSH 연결을 종료한 뒤 다시 접속합니다.

### 저장소 및 환경변수

```bash
git clone https://github.com/KTCloud-Crypto/KTCloud-Crypto.git
cd KTCloud-Crypto
cp .env.example .env
nano .env
```

EC2에서는 브라우저가 접근할 FastAPI 주소를 지정합니다.

```env
VITE_API_BASE_URL=http://EC2_PUBLIC_IP:8000
ENVIRONMENT=production
LIVE_TRADING_ENABLED=false
```

AWS 보안 그룹에서 테스트 단계에 필요한 포트를 본인 IP로 제한해 허용합니다.

- `22`: SSH
- `5173`: 현재 Vite 프론트엔드
- `8000`: FastAPI

현재 Compose는 MVP 개발·검증용 구성입니다. 정식 운영에서는 Vite 개발 서버와 Uvicorn `--reload` 대신 정적 프론트 배포, reverse proxy, HTTPS 구성이 필요합니다.

### 실행

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
docker compose logs --tail=100 strategy-worker
```

## 11. 코드 업데이트

배포 전 현재 상태와 변경 파일을 확인합니다.

```bash
git status -sb
git fetch origin develop
git pull --ff-only origin develop
```

DB 변경이 포함됐다면 새 Alembic 리비전의 `upgrade`와 `downgrade`를 검토하고, DB 백업 후 `alembic upgrade head`를 적용합니다.

```bash
docker compose up --build -d
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 strategy-worker
```

## 12. 중지와 데이터 주의사항

컨테이너만 중지하고 DB volume 유지:

```bash
docker compose down
```

다시 실행:

```bash
docker compose up -d
```

다음 명령은 DB volume까지 삭제합니다.

```bash
docker compose down -v
```

> `down -v`는 테스트 데이터를 완전히 초기화할 때만 사용합니다. 운영 서버에서는 사용하지 마세요.

## 13. 문제 확인

```bash
# 전체 상태
docker compose ps

# API
docker compose logs -f backend

# 전략 계산, 주문, Telegram
docker compose logs -f strategy-worker

# DB
docker compose logs -f db

# frontend
docker compose logs -f frontend
```

Upbit 잔고가 조회되지 않으면 다음을 확인합니다.

- Access Key와 Secret Key
- Upbit API Key 권한
- Upbit 허용 IP와 현재 서버 공인 IP
- `MASTER_ENCRYPTION_KEY`가 기존 DB 암호화에 사용한 값과 같은지
- backend 및 strategy-worker 로그
