# 설계 문서 (KTCloud-Crypto 백엔드/프론트엔드)

TradingView 웹훅 기반 Upbit 자동매매 서비스의 구조, API, 진행 상태를 정리한 문서.

## 1. 전체 구조

```
backend/
  app/
    main.py                  FastAPI 앱, 라우터 등록, 테이블 생성
    core/
      config.py               환경변수 설정 (pydantic-settings)
      database.py              SQLAlchemy engine/session, get_db 의존성
    models/
      user.py                  User (webhook_token/bot_enabled/telegram_chat_id 포함)
      api_key.py                ApiKey (Fernet 암호화 저장)
      position.py                Position (중복 매수/매도 방지, 현재 상태)
      trade.py                    Trade (매매 실행 이력)
    schemas/                    Pydantic 요청/응답 스키마
    services/
      security.py                비밀번호 해시(PBKDF2), JWT 발급/검증 (직접 구현, 외부 라이브러리 미사용)
      crypto.py                   Fernet 암복호화 (거래소 API Key 저장용)
      upbit.py                    Upbit 키 검증(JWT 서명, urllib), 실계좌 잔고 조회(get_accounts)
      upbit_service.py             Upbit 매수/매도 (pyupbit, 호가 기반 지정가 주문)
      telegram.py                   텔레그램 알림 발송 (HTTP 직접 호출, 폴링 봇 없음)
    api/
      auth.py                      회원가입/로그인/로그아웃, get_current_user 의존성
      users.py                      프로필, 거래소 API Key 등록, 웹훅 URL 발급
      positions.py                   /positions(DB), /positions/balance(실시간)
      trades.py                       거래내역 조회
      webhook.py                       TradingView 웹훅 수신 → 매매 실행
      health.py                         헬스체크

frontend/
  src/
    api/client.js              JWT 저장/전달, 공통 fetch 래퍼, 401 자동 로그아웃
    pages/                     LoginPage, SignupPage, DashboardPage
    components/
      layout/                  Sidebar, Topbar (실제 로그인 유저 정보 표시)
      dashboard/                BalancePanel, PositionsPanel, TradesPanel, WebhookPanel
```

DB는 PostgreSQL, ORM은 SQLAlchemy(Column 스타일). 실행은 Docker Compose(`db` + `backend` + `frontend` 3개 서비스).

## 2. 데이터 모델

| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `user` | `username`, `password`, `nickname`, `webhook_token`, `bot_enabled`, `telegram_chat_id` | 계정. `webhook_token`은 가입 시 자동 발급(uuid4) |
| `api_key` | `user_id`(1:1), `encrypted_access_key`, `encrypted_secret_key` | Fernet으로 암호화해 저장 |
| `position` | `user_id`, `ticker`, `status`("long"/None) | `(user_id, ticker)` unique. 중복 매수/매도 방지용 |
| `trade` | `user_id`, `ticker`, `action`, `price`, `volume`, `status`, `raw_response` | 매매 실행 이력 |

마이그레이션 도구(Alembic) 미도입. `Base.metadata.create_all()`로 앱 시작 시 누락된 테이블만 생성하며, 기존 컬럼 변경/삭제는 반영되지 않는다 (스키마 변경 시 로컬은 `docker compose down -v`로 재생성 필요).

## 3. API 목록

인증이 필요한 엔드포인트는 `Authorization: Bearer <JWT>` 헤더 필요.

| Method | Path | 인증 | 설명 |
|---|---|---|---|
| POST | `/auth/signup` | X | 회원가입, Upbit API Key 라이브 검증 후 암호화 저장 |
| POST | `/auth/login` | X | 로그인, JWT 반환 |
| POST | `/auth/logout` | O | 로그아웃 (토큰 검증만, 서버측 무효화 없음) |
| GET | `/users/me` | O | 내 프로필 조회 |
| PUT | `/users/me` | O | `telegram_chat_id`, `bot_enabled` 수정 |
| POST | `/users/me/exchange-key` | O | Upbit API Key 등록/갱신 (암호화 저장) |
| GET | `/users/me/webhook-url` | O | 내 전용 웹훅 URL 조회 |
| POST | `/webhook/{token}` | X (토큰이 인증 역할) | TradingView 신호 수신 → 매수/매도 실행 |
| GET | `/positions` | O | 내 포지션 목록 (DB) |
| GET | `/positions/balance` | O | Upbit 실계좌 잔고 실시간 조회 |
| GET | `/trades` | O | 내 거래내역 (최근 200건) |
| GET | `/health` | X | 헬스체크 |

Swagger UI: `http://localhost:8000/docs`

### 웹훅 요청 형식

```json
{"action": "buy", "ticker": "KRW-BTC"}
{"action": "sell", "ticker": "KRW-BTC"}
```

JSON 파싱 실패 시 TradingView 기본 plain text 템플릿(한국어/영어)도 정규식으로 파싱해서 처리한다.

## 4. 완성된 부분

- 회원가입/로그인 (JWT — 직접 구현한 HS256, PBKDF2 해시), DB 적재 정상
- 사용자별 Upbit API Key 등록/암호화 저장(Fernet)
- 사용자별 고유 웹훅 URL로 TradingView 신호 라우팅
- 웹훅 수신 → Upbit 매수/매도(호가 기반 지정가 주문) → 포지션/거래내역 DB 기록 → 텔레그램 알림(선택)
- 실계좌 잔고 실시간 조회 (`/positions/balance`)
- 프론트엔드 로그인/대시보드 실제 백엔드 연동 (JWT 저장, 라우트 가드, 잔고/포지션/거래내역/웹훅 URL 실데이터 표시)
- Docker Compose로 FastAPI + PostgreSQL + React 통합 실행
- 웹훅 → 실주문 실패 시 정확히 `failed`로 기록되는지 실계좌 테스트로 검증 완료

## 5. 안 된 부분 / 알려진 제약

- **텔레그램 봇 명령어 없음** — `/start /stop /status /balance /help` 같은 폴링 명령 처리 미구현. 알림 발송(단방향)만 있음
- **TradingView 실연동 미검증** — 로컬(`localhost:8000`)은 외부에서 접근 불가. ngrok 또는 실서버 배포 필요
- **DB 마이그레이션 도구 없음** — `Base.metadata.create_all()`로 앱 시작 시 테이블 생성. 컬럼 추가/변경 시 수동 처리 필요 (Alembic 미도입)
- **자동 테스트 없음** — 전부 수동(curl/Swagger/브라우저)으로 검증
- **거래소는 Upbit만 지원**
- **레이트리밋/재시도 로직 없음** — Upbit API 호출 실패 시 단순 실패 처리, 재시도 없음
- **로그아웃이 서버측 토큰 무효화를 하지 않음** — JWT는 만료 전까지 유효 (블랙리스트 없음)

## 6. 앞으로 해야 할 것 (우선순위 제안)

1. **실서버 배포 또는 ngrok으로 TradingView 웹훅 실연동 검증**
2. **텔레그램 chat_id 연결 UX** — 프론트에서 등록 플로우 설계
3. **텔레그램 명령어(폴링 봇)** — `/start /stop /status /balance` 등
4. **Alembic 도입** — 스키마 변경이 잦아지기 전에 마이그레이션 체계 준비
5. **테스트 코드** — 최소한 웹훅 파싱 로직(plain text fallback)에 대한 단위 테스트
6. **레이트리밋/재시도** — Upbit API 실패 시 재시도 로직

## 7. 보안 주의사항

- `MASTER_ENCRYPTION_KEY`가 유출되면 모든 사용자의 거래소 키가 복호화 가능해지므로, 서버 환경변수로만 관리하고 별도 채널(팀 시크릿 매니저 등)로 공유할 것
- `SECRET_KEY`(JWT 서명 키)도 동일하게 취급
- `.env`는 절대 커밋하지 말 것 (`.env.example`만 커밋)
- 로컬 개발용 `MASTER_ENCRYPTION_KEY`를 실서버에 그대로 쓰지 말 것 (서버별로 새로 발급)
