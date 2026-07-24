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

- 회원가입 시 Upbit API Key 검증 및 암호화 저장
- JWT 로그인과 사용자 데이터 분리
- 로그인 직후 모의·실전 핵심 상태를 보여주는 통합 홈
- 모의투자와 실전투자의 전략 설정·포지션·실행 기록 분리
- SMA, RSI, MACD, 볼린저 밴드, 돈치안 채널 전략
- BTC, ETH, XRP, SOL, DOGE, TRX 6종목 지원
- 사용자·모드·종목·전략 조합별 분봉, 투자 비율, 손절률, 목표 수익률 설정
- Upbit WebSocket 6종목 체결 데이터 기반 분봉과 지표 계산
- 모의계좌 및 Upbit 실제 시장가 주문
- 전략별 포지션과 평균 매수가 계산
- Telegram 연동, 주문·체결·청산 알림
- 실제 Upbit 잔고와 전략 기록 비교 및 동기화
- 중복 주문 방지와 worker 중단 시 미완료 주문 복구
- 실전투자·모의투자를 분리한 FIFO 수익 분석과 종목별 시각화
- 닉네임·비밀번호·Upbit API Key를 관리하는 계정 설정

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
| `strategy-worker` | 일반 Python 비동기 프로그램 | 시세 수신, 전략 계산, 주문, Telegram, 반복 감시 |
| `db` | PostgreSQL 15 | 사용자 설정과 주문·전략 기록 영속화 |

`backend`와 `strategy-worker`는 같은 Python 코드와 이미지를 사용하지만 실행 명령과 역할이 다릅니다.

## 빠른 시작

### 1. 환경변수 생성

```bash
cp .env.example .env
```

Fernet 키를 생성해 `.env`의 `MASTER_ENCRYPTION_KEY`에 입력합니다.

```bash
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

`MASTER_ENCRYPTION_KEY`는 Access Key와 Secret Key를 합친 값이 아닙니다. DB에 각각 암호화된 두 값을 암호화·복호화할 때 사용하는 서버 공용 열쇠입니다. 운영 중 키를 바꾸거나 분실하면 기존 API Key를 복호화할 수 없습니다.

### 2. 컨테이너 실행

```bash
docker compose up --build -d
docker compose ps
```

### 3. 접속 및 상태 확인

```bash
curl http://localhost/healthz
curl http://localhost/api/health
```

```json
{"status":"ok"}
```

브라우저:

```text
http://localhost
```

## 실제 주문 안전 스위치

실전 모드를 선택했더라도 서버의 전역 스위치가 꺼져 있으면 실제 주문을 실행하지 않습니다.

```env
LIVE_TRADING_ENABLED=false
```

모의투자와 API Key·Telegram 연결을 먼저 검증하고 실제 주문을 허용할 때만 `true`로 변경합니다.

```bash
docker compose up -d --force-recreate backend strategy-worker
```

투자 비율은 남은 KRW 잔고의 비율이 아니라 전체 운용자산에서 각 종목·전략 조합에 배정할 최대 비율입니다. 모의와 실전 각각에서 모든 종목의 활성 전략 합계는 100%를 넘을 수 없습니다. 실전 주문은 실제 자산을 사용하므로 종목, 투자 비율과 손절·익절 설정을 반드시 확인해야 합니다.

## Telegram

`.env`에 BotFather가 발급한 정보를 입력합니다.

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
```

대시보드에서 1회용 코드를 발급한 후 봇 채팅에 전송합니다.

```text
/start 123456
```

실제 Upbit 수량과 전략 포지션 기록을 비교하려면 다음 명령을 사용합니다.

```text
/sync
```

`/sync`의 배정·차감은 내부 전략 기록만 조정하며 새로운 Upbit 주문을 실행하지 않습니다.

다종목 Telegram 전략 명령은 모드·종목·전략을 함께 구분합니다.

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

## 현재 범위와 남은 운영 작업

기본 MVP 기능과 단위·빌드 검사는 완료됐습니다. 다음 항목은 운영 배포 단계에서 추가 검증이 필요합니다.

- 장시간 WebSocket 및 자연 전략 신호 실행
- EC2 운영 배포 자동화
- HTTPS와 도메인
- AWS 비밀정보 저장소
- PostgreSQL 정기 백업
- 외부 모니터링 및 worker 고가용성
