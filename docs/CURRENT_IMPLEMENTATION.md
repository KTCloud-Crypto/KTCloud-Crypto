# SignalTrade 현재 구현 및 병합 상태

기준일: 2026-07-24

작업 브랜치: `feat/19`

기준 코드: `origin/develop` 최신 내용을 `feat/19`에 병합한 상태

## 1. 현재 제품 방향

SignalTrade는 TradingView 웹훅을 사용하지 않습니다. Upbit WebSocket과 REST API를 사용해 자체 전략 엔진이 시세를 수신·계산하고, 모의투자 또는 실전투자 주문을 처리합니다.

```text
Upbit WebSocket → strategy-worker → 전략 계산 → 모의 체결 또는 Upbit 실제 주문
브라우저 → FastAPI → 사용자 설정·계좌·전략·분석 조회
```

제거된 범위:

- TradingView 웹훅 URL 발급과 수신 API
- 웹훅 활성화 설정과 처리 이력
- Nginx의 `/webhook/` 전용 프록시와 요청 제한 설정

유지되는 Upbit 기능:

- 회원가입 및 설정 화면의 API Key 검증
- Access/Secret Key 암호화 저장
- 실계좌 잔고와 현재가 조회
- 자체 전략 기반 시장가 주문
- 주문 사전 검사, 중복 방지, 미완료 주문 복구
- 실제 잔고와 전략 포지션 기록 비교·동기화

## 2. 화면 구성

| 경로 | 화면 | 주요 기능 |
|---|---|---|
| `/dashboard` | 통합 홈 | 모의·실전투자 핵심 상태와 준비 상태 |
| `/dashboard/simulated` | 모의투자 | 모의 투자금, 전략, 포지션, 실행 기록 |
| `/dashboard/live` | 실전투자 | Upbit 잔고, 전략, 실제 주문과 동기화 |
| `/analytics` | 사용자 분석 | 실전·모의 전환, 기간별 수익, 원형·선·막대 그래프 |
| `/settings` | 계정 설정 | 닉네임, 비밀번호, Upbit API Key 관리 |

사이드바 순서:

```text
홈
모의투자
실전투자
사용자 분석
계정 설정
```

## 3. 사용자 분석

사용자 분석은 `실전투자 / 모의투자`를 분리합니다.

### 실전투자

- `trade` 테이블의 사용자별 성공 체결 사용
- 매수 로트를 FIFO 방식으로 매도 체결과 매칭
- 오늘, 이번 주, 이번 달, 전체 기간 제공
- 실현손익, 매도 승률, 체결 건수, 총 거래 규모 표시
- 최근 30일 누적 손익 선 그래프
- 종목별 거래 비중 원형 그래프
- 종목별 실현손익 막대 그래프

Upbit 수수료 원본이 현재 `trade`에 별도 저장되지 않으므로 실전 분석 손익에는 수수료가 포함되지 않습니다.

### 모의투자

- `strategy_execution.mode = simulated` 기록 사용
- `simulated_success` 상태의 체결만 성공 거래로 계산
- `average_price`, `executed_volume`을 우선 사용
- 실전투자와 동일한 FIFO 및 시각화 구조 제공

분석 API:

```text
GET /analytics?mode=live
GET /analytics?mode=simulated
```

## 4. 계정 설정

제공 기능:

- 닉네임 변경
- 현재 비밀번호 확인 후 새 비밀번호 설정
- 비밀번호 변경 후 프론트엔드 토큰 삭제 및 재로그인
- Upbit API Key 등록·교체 전 유효성 검증
- API Key 암호화 저장
- 계정 비밀번호 확인 후 저장된 API Key 연결 해제
- API Key 연결 해제 시 자동매매 중지

Telegram 연결은 계정 설정에서 Chat ID를 직접 입력하지 않습니다. 투자 화면에서 10분 유효 일회용 코드를 발급하고 Telegram 봇에 `/start 코드`를 전송하는 develop 방식으로 유지합니다.

## 5. 컨테이너와 DB

현재 Compose 서비스:

| 서비스 | 상태/역할 |
|---|---|
| `db` | PostgreSQL 15 |
| `migrate` | 시작 시 Alembic 적용 후 정상 종료 |
| `backend` | FastAPI, 로컬 포트 8000 |
| `strategy-worker` | 시세·전략·주문·Telegram 처리 |
| `frontend` | Nginx, 로컬 포트 80/443 |

`VITE_API_BASE_URL`은 런타임 환경변수가 아니라 프론트 이미지 빌드 인자로 전달합니다.

### 기존 로컬 DB 주의사항

이전 로컬 DB는 Alembic 도입 전 생성되어 `user` 등의 테이블은 있지만 마이그레이션 이력이 없습니다. 최신 초기 마이그레이션을 그대로 적용하면 중복 테이블 오류가 발생합니다.

기존 데이터는 삭제하지 않고 보존했으며, 현재 확인용 서버는 별도 Compose 프로젝트를 사용합니다.

```bash
docker compose -p ktcloud-crypto-develop up -d --build
```

현재 확인 주소:

```text
웹         http://localhost
API 상태   http://localhost:8000/health
분석       http://localhost/analytics
설정       http://localhost/settings
```

## 6. 병합 및 검증 결과

`origin/develop` 병합 과정에서 최신 전략·모의투자·실전투자 구조를 기준으로 충돌을 해결했습니다. 구형 대시보드 패널과 SQL 마이그레이션은 새 Alembic 구조와 중복되어 사용하지 않습니다.

검증 결과:

- Alembic 초기 마이그레이션부터 head까지 적용 성공
- `alembic check`: 새 마이그레이션 필요 없음
- 백엔드 전체 테스트: 57개 통과
- 사용자 분석 단위 테스트 통과
- 프론트 ESLint 통과
- Vite production build 성공
- backend/frontend Docker 이미지 build 성공
- develop 전용 로컬 컨테이너 정상 실행

## 7. 배포 전 확인 사항

- `LIVE_TRADING_ENABLED=false`로 모의투자부터 검증
- 운영 DB 백업 후 Alembic 적용
- 기존 운영 DB가 Alembic 이전 스키마라면 별도 전환 마이그레이션 작성
- 운영 환경의 `SECRET_KEY`, `MASTER_ENCRYPTION_KEY`, DB 비밀번호 재확인
- Upbit API Key의 허용 IP와 주문 권한 확인
- HTTPS 인증서와 도메인 설정 확인
- 장시간 strategy-worker 및 Upbit WebSocket 안정성 확인

## 8. Git 상태

병합 충돌은 모두 해결됐지만 이 문서 작성 시점의 변경은 아직 커밋되지 않았습니다. 병합 전 로컬 작업은 안전을 위해 stash에 백업되어 있습니다.

커밋 전 권장 명령:

```bash
git status -sb
git diff --cached --check
docker compose -p ktcloud-crypto-develop ps
```
