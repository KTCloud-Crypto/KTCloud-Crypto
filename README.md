# KTCloud-Crypto

TradingView 웹훅 신호를 받아 Upbit 자동매매를 실행하고, 사용자별 포지션·거래내역을 관리하는 웹 서비스.
FastAPI + PostgreSQL 백엔드, React(Vite) 프론트엔드로 구성되며 Docker Compose로 함께 실행한다.

## Docker Compose 실행

루트 디렉토리에서 실행합니다.

```bash
cp .env.example .env
```

`.env`에 `MASTER_ENCRYPTION_KEY`를 반드시 채워야 합니다 (미설정 시 Compose 실행 실패).

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

텔레그램 알림을 쓸 경우 `TELEGRAM_BOT_TOKEN`도 채웁니다 (선택, 비워두면 알림만 무시됨).

```bash
docker compose up --build -d
```

## 실행 상태 확인

```bash
docker compose ps
```

정상 상태 예시:

```text
frontend   Up
backend    Up healthy
db         Up healthy
```

```bash
curl http://localhost/healthz
curl http://localhost/api/health
```

정상 응답:

```json
{"status":"ok"}
```

## Database 확인

```bash
docker compose exec db psql -U postgres -d fastapi_db -c '\dt'
```

정상 테이블 예시:

```text
api_key
position
trade
user
```

## API 개요

- `POST /auth/signup` — 회원가입 + Upbit API Key 등록 (라이브 검증 후 암호화 저장)
- `POST /auth/login` — 로그인, JWT 발급
- `POST /auth/logout` — 로그아웃 (토큰 검증만 수행)
- `GET/PUT /users/me` — 내 프로필 조회/수정 (`telegram_chat_id`, `bot_enabled`)
- `POST /users/me/exchange-key` — Upbit API Key 등록/갱신 (암호화 저장)
- `GET /users/me/webhook-url` — 내 전용 TradingView 웹훅 URL 조회
- `POST /webhook/{token}` — TradingView 웹훅 수신 → Upbit 매수/매도 실행
- `GET /positions` — 내 포지션 목록 (DB 기록, 웹훅 매매 결과)
- `GET /positions/balance` — Upbit 실계좌 잔고 실시간 조회
- `GET /trades` — 내 거래내역 조회 (최근 200건)

`/users/*`, `/positions*`, `/trades` 요청은 `Authorization: Bearer <JWT>` 헤더가 필요합니다.

전체 구조/데이터 모델은 [`DESIGN.md`](./DESIGN.md), 현재 상태·이슈는 [`CONTEXT.md`](./CONTEXT.md) 참고.

## TradingView 웹훅 설정

1. 로그인 후 `GET /users/me/webhook-url`로 본인 웹훅 URL을 확인한다.
2. TradingView 알림(Alert) 설정의 웹훅 URL에 `https://<서버주소>/webhook/{내 토큰}`을 입력한다.
3. 메시지 형식(JSON):

```json
{"action": "buy", "ticker": "KRW-BTC"}
{"action": "sell", "ticker": "KRW-BTC"}
```

TradingView 기본 plain text 템플릿(한국어/영어)도 자동 인식된다.

> 로컬 개발 환경(`localhost:8000`)은 TradingView가 접근할 수 없습니다. ngrok 등으로 외부 노출하거나 실서버에 배포해야 실제 연동이 가능합니다.

## Frontend 확인

```bash
docker compose logs -f frontend
```

정상 로그 예시:

```text
VITE ready
frontend   Up healthy
```

브라우저에서 접속:

```text
http://localhost
```

## 자주 쓰는 명령어

```bash
# 전체 로그 확인
docker compose logs -f

# backend 로그 확인
docker compose logs -f backend

# db 로그 확인
docker compose logs -f db

# 컨테이너 중지
docker compose down

# 컨테이너와 DB 볼륨까지 삭제
docker compose down -v
```
