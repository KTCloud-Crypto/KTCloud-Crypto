# KTCloud-Crypto 현재 상태 컨텍스트

## 프로젝트 개요

FastAPI 기반 Upbit 자동매매 웹 서비스. TradingView 웹훅 수신 → Upbit 주문 → 텔레그램 알림(선택).
회원가입/로그인(JWT), 사용자별 Upbit API Key(암호화 저장), 사용자별 웹훅 URL, PostgreSQL 기반 포지션/거래내역 관리를 갖춘 멀티유저 구조.

원래 팀원별로 API를 나눠 작업하던 중, `feat/9` 브랜치에서 백엔드 구조 전체를 개편하고 프론트엔드를 실제 백엔드에 연동하는 작업을 한 사람이 맡아 진행했다 (`ho-v1.0` 사내 레퍼런스 구현을 기반으로 재구성).

## 인증 정보 (.env)

`.env.example` 참고. 실제 값은 `.env`에만 저장하고 절대 커밋하지 않는다.

```
DATABASE_URL=
SECRET_KEY=
MASTER_ENCRYPTION_KEY=
TELEGRAM_BOT_TOKEN=
UPBIT_API_BASE_URL=https://api.upbit.com
```

- `SECRET_KEY`: 앱 JWT 서명 키 (`app/services/security.py`에서 HS256 직접 구현)
- `MASTER_ENCRYPTION_KEY`: 거래소 API Key 암호화용 Fernet 키. `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`로 생성
- `TELEGRAM_BOT_TOKEN`: 선택. 비워두면 알림 발송 함수가 조용히 무시함

## 핵심 아키텍처 변경 사항 (2026-07-16, feat/9)

### DB 모델 (`backend/app/models/`)

- `User`: username/password(PBKDF2 해시)/nickname 기존 유지 + `webhook_token`(가입 시 자동 발급), `bot_enabled`, `telegram_chat_id` 추가
- `ApiKey`: 기존 평문 저장(`access_key`/`secret_key`)에서 `encrypted_access_key`/`encrypted_secret_key` (Fernet 암호화)로 전환. `user_id` unique(1인 1키)
- `Position` 신규: `(user_id, ticker)`별 보유 상태. 기존에 없던 테이블
- `Trade` 신규: 매수/매도 실행 결과 이력. 기존 `TradeHistory`(stock_name/buy_amount/sell_amount 구조)를 대체
- `LastSignal`, `TradeHistory` 테이블은 실제로 아무 API에서도 쓰이지 않고 있어서 제거함

### 인증 (`backend/app/api/auth.py`, `backend/app/services/security.py`)

- 기존 회원가입/로그인 로직(계정명 방식, PBKDF2 해시, 직접 구현한 HS256 JWT) 그대로 유지
- 회원가입 시 업비트 API로 라이브 키 검증 후, 키를 암호화해서 저장하도록만 변경
- `get_current_user` 의존성으로 `/users/*`, `/positions*`, `/trades` 보호

### 웹훅 (`backend/app/api/webhook.py`)

- URL 경로에 `{token}`을 받아 `User.webhook_token`으로 사용자 식별
- 파싱 로직(JSON/plain text fallback, suffix 제거)은 `ho-v1.0`과 동일
  - 정규식: `(?:order|오더)\s+(buy|sell).*?(?:on|필드 온)\s+(\w+)`
  - 제거 suffix 목록: `("USDT", "USD", "BUSD", "PERP", "KRW")`
- 매수: `Position.status == "long"` 이면 무시 (중복 방지)
- 매도: `Position.status != "long"` 이면 무시
- 매수/매도 성공/실패 모두 `Trade` 테이블에 기록

### app/services/upbit_service.py (호가 기반 지정가)

- `pyupbit` 라이브러리 사용, 함수는 `access_key`/`secret_key`를 인자로 받음 (사용자별 키)
```python
BUY_RATIO = 0.9995

# 매수: 매도1호가로 지정가 주문
async def buy_market_order(ticker, access_key, secret_key): ...

# 매도: 매수1호가로 지정가 주문
async def sell_market_order(ticker, access_key, secret_key): ...
```
- 회원가입 키 검증(`app/services/upbit.py`, urllib 기반)과는 별도 모듈. `/positions/balance`(실시간 잔고 조회)는 `upbit.py`의 `get_accounts` 사용

### 텔레그램 (`backend/app/services/telegram.py`)

- `ho-v1.0`과 달리 폴링 봇(명령어 처리)은 구현하지 않음 — 스코프 축소
- 단방향 알림 발송만 구현 (Telegram Bot API에 직접 HTTP POST, 토큰/chat_id 없으면 조용히 무시)

## 발견 및 해결한 이슈

| 이슈 | 원인 | 해결 |
|------|------|------|
| 웹훅 매수 실패인데 `trade.status`가 `success`로, `position`이 `long`으로 잘못 기록됨 | Upbit가 에러를 담은 dict(`{"error": {...}}`)를 반환해도 `if result:`가 truthy로 통과 (ho-v1.0 원본에도 있던 버그) | `if result and not result.get("error"):`로 수정 |
| DB 스키마 변경(컬럼명/테이블 구조) 후 `create_all()`이 기존 컬럼을 갱신 못함 | 마이그레이션 도구 미도입 | 로컬 개발 중이라 `docker compose down -v`로 볼륨 초기화 후 재생성 (운영 DB에는 이 방법 사용 불가, Alembic 도입 필요) |

## 실계좌 테스트 기록

- 테스트 계정 `testho`로 실제 업비트 소액(KRW 5,000원) 입금 후 웹훅 매수 신호 전송
- 잔고 부족(`invalid_volume_bid`)으로 실패 → 수정 전에는 `success`로 잘못 기록되던 것을 위 버그 수정 후 `failed`로 정확히 기록되는 것 확인
- 성공 케이스(실제 체결)는 아직 검증 안 됨

## TradingView 웹훅 설정

### 지원하는 메시지 포맷 (둘 다 자동 처리)

**JSON 형식**:
```json
{"action":"{{strategy.order.action}}","symbol":"{{ticker}}","price":"{{close}}"}
```

**Plain text 기본 템플릿** (한국어/영어 둘 다 OK):
```
Date RSI Strategy v3: 오더 {{strategy.order.action}} @ {{strategy.order.contracts}} 필드 온 {{ticker}}. 뉴 스트래티지 포지션은 {{strategy.position_size}}
```

- `price` 필드는 사용 안 함 (orderbook에서 직접 조회하므로 불필요)
- 사용자는 `GET /users/me/webhook-url`로 발급받은 URL을 TradingView 알림 웹훅에 등록한다

### 로컬 환경 제약

- 지금은 `localhost:8000`에서만 돌기 때문에 TradingView(외부)가 웹훅을 보낼 수 없음
- 실연동하려면 ngrok으로 임시 터널을 열거나, 실서버(예: 네이버클라우드 — [`SETUP.md`](./SETUP.md) 참고)에 배포해야 함

## 주의사항

- 포지션/거래내역은 PostgreSQL에 영구 저장되므로 컨테이너 재시작에도 유실되지 않음
- `locked` 잔고(미체결 지정가 주문)는 `get_balance()` 기준으로 잡히지 않을 수 있음
- KRW 잔고 부족 시 `invalid_volume_bid`/`UnderMinTotalBid` 에러로 매수 실패 (Upbit 최소 주문 5,000원)
- 로그아웃은 클라이언트 토큰 삭제 + 서버 검증뿐, JWT 자체는 만료 전까지 계속 유효함 (블랙리스트 없음)
