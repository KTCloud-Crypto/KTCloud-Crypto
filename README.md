# SignalTrade

SignalTrade는 Upbit API와 실시간 시세를 이용해 사용자별 전략을 계산하고 모의투자 또는 실제 주문을 실행하는 자동매매 웹 서비스입니다.

```text
React + Vite ──HTTP── FastAPI + Uvicorn
                           │
                       PostgreSQL
                           ▲
                           │
                    strategy-worker
                     │           │
               Upbit API/WS   Telegram
```

## 주요 기능

- Upbit API Key 검증 및 암호화 저장
- JWT 로그인과 모의·실전 분리된 사용자 상태
- 6종목 지원과 종목·전략 조합별 설정
- SMA, RSI, MACD, 볼린저 밴드, 돈치안 채널 전략
- Upbit WebSocket 기반 분봉·지표 계산과 주문 실행
- Telegram 알림, 잔고 동기화, 중복 주문 방지, 실행 복구
- FIFO 수익 분석과 계정 설정

## 화면 구조

```text
로그인
  └── 통합 홈
      ├── 모의투자
      │   ├── 종목 선택과 전략 관리
      │   ├── 모의계좌와 포지션
      │   └── 신호·실행 내역
      └── 실전투자
          ├── 종목 선택과 전략 관리
          ├── Upbit 잔고와 포지션
          ├── 잔고 동기화
          └── 신호·주문·거래 내역
      ├── 사용자 분석
      │   ├── 실전투자·모의투자 전환
      │   ├── 기간별 실현손익과 승률
      │   └── 종목별 거래 비중·손익 그래프
      └── 계정 설정
          ├── 닉네임·비밀번호 변경
          └── Upbit API Key 검증·교체·연결 해제
```

## 컨테이너 역할

| 서비스 | 실행 프로그램 | 역할 |
|---|---|---|
| `frontend` | React + Vite | 사용자 화면 |
| `backend` | FastAPI + Uvicorn | 인증, 설정, 조회 및 조작 API |
| `migrate` | Alembic | DB 스키마 선행 적용 후 종료 |
| `strategy-worker` | Python 비동기 프로세스 | 시세 수신, 전략 계산, 주문, Telegram 감시 |
| `db` | PostgreSQL 15 | 사용자 설정과 주문·전략 기록 저장 |

`backend`와 `strategy-worker`는 같은 Python 코드와 이미지를 사용하지만 실행 명령과 역할이 다릅니다. `migrate`는 `backend`보다 먼저 실행되는 일회성 컨테이너입니다.

## 빠른 시작

설치와 환경변수 값은 [SETUP.md](SETUP.md)를 따른다.

```bash
docker compose up --build -d
docker compose ps
```

접속:

```bash
http://localhost
```

## 실제 주문 안전 스위치

```env
LIVE_TRADING_ENABLED=false
```

실전 주문을 허용할 때만 `true`로 바꾸면 된다.

## Telegram

`.env`에 BotFather가 발급한 값을 입력합니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
```

대시보드에서 1회용 코드를 발급한 뒤 봇 채팅에 전송합니다.

```text
/start 123456
```

`/sync`는 Upbit 수량과 전략 기록을 맞추되 새 주문은 실행하지 않는다.

```text
/paper_btc_sma
/live_eth_rsi
```

## 개발 검사

```bash
docker compose exec backend python -m pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose build
```

GitHub Actions는 `develop` 대상 PR과 `develop` push에서 다음을 검사합니다.

- backend pytest
- frontend ESLint
- frontend production build
- backend/frontend Docker 이미지 build

## 자주 사용하는 명령

```bash
# 상태
docker compose ps

# 전체 로그
docker compose logs -f

# 자동매매 worker 로그
docker compose logs -f strategy-worker

# PostgreSQL 접속
docker compose exec db psql -U postgres -d fastapi_db

# 중지(DB volume 유지)
docker compose down

# 재빌드
docker compose up --build -d
```

> `docker compose down -v`는 PostgreSQL volume도 삭제합니다. 운영 서버나 보존할 데이터가 있는 환경에서는 사용하지 마세요.

## 문서

- [설치 및 실행 방법](SETUP.md)
- [프로젝트 구조와 데이터 흐름](docs/ARCHITECTURE_AND_USAGE.md)
- [MVP 안정화 및 다종목 확장 기록](docs/MVP_STABILIZATION.md)
- [현재 구현 및 병합 상태](docs/CURRENT_IMPLEMENTATION.md)
- [백엔드 구조](backend/README.md)
