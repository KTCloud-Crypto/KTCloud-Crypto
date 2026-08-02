# SignalTrade MVP 안정화 작업 정리

이 문서는 기본 기능 구현 이후 주문과 포지션을 실제 서비스 흐름에 맞게 안정화한 작업을 `문제 → 변경 → 해결 결과 → 검증` 순서로 정리한다.

## 1. 전략 해제와 포지션 생명주기

### 문제

포지션을 보유한 전략을 즉시 해제하면 이후 매도 신호와 자동 청산이 중단된다. 반대로 해제를 무조건 막으면 사용자가 전략을 종료할 수 없다.

### 변경

- 모의와 실전 전략 설정을 `mode`로 분리
- 보유 포지션이 있을 때 해제 위험 경고
- 사용자 확인 후 강제 해제 허용
- 해제 후에도 포지션과 수동 전량 매도 기능 유지
- 화면에 `전략 해제됨 · 포지션 보유 중` 표시

### 해결 결과

사용자가 위험을 이해하고 전략을 해제할 수 있으며, 남은 포지션을 잃어버리지 않고 수동으로 정리할 수 있다.

## 2. 의미 없는 중복 신호 처리

### 문제

이미 포지션이 있는데 매수 신호가 반복되거나, 포지션 없이 매도 신호가 발생하면 실패 기록과 Telegram 알림이 계속 쌓였다.

### 변경

- 보유 포지션이 있는 동일 전략의 추가 매수 차단
- 포지션이 없는 전략의 매도 차단
- 정상적으로 건너뛴 신호는 `skipped` 또는 `simulated_skipped`로 구분
- 건너뛴 신호에는 실패 Telegram 알림을 보내지 않음

### 해결 결과

전략은 기본적으로 `매수 → 보유 → 매도 → 다음 매수` 흐름을 유지하고, 사용자에게 의미 없는 실패 알림을 보내지 않는다.

## 3. 포지션 청산 수단

### 문제

매수 후 반대 신호가 오랫동안 발생하지 않으면 포지션이 무기한 유지될 수 있었다.

### 변경

- 전략별 손절률 설정
- 전략별 목표 수익률 설정
- 빈 값 또는 0%는 자동 청산 미사용 처리
- 전략별 수동 전량 매도
- worker가 현재가와 평균 매수가를 비교해 자동 청산 신호 생성
- 손절, 목표 수익률, 수동 매도 이유를 Telegram과 실행 내역에 표시

### 해결 결과

반대 전략 신호를 기다리지 않아도 사용자가 설정한 위험 범위나 수동 판단으로 포지션을 종료할 수 있다.

### 검증

모의투자에서 목표 수익률, 손절, 수동 전량 매도와 Telegram 메시지를 각각 확인했다.

## 4. 실전 주문 상태와 최종 체결 정산

### 문제

Upbit 주문 접수 응답만으로 성공을 판단하면 부분 체결, 체결 대기, 잔여 예약금 취소 상태를 정확하게 표현할 수 없다.

### 변경

- 주문 상태를 `submitted`, `partially_filled`, `success`, `cancelled`, `failed`로 정규화
- 체결 내역의 거래대금과 수량으로 평균 체결가 계산
- worker가 5초마다 미완료 주문 UUID 재조회
- 최종 상태, 체결량, 평균가, 거래 내역과 포지션 갱신
- 접수 알림과 최종 정산 알림을 별도로 관리

### 해결 결과

주문 접수와 실제 체결을 구분하며, 늦게 끝난 주문도 DB와 Telegram에 최종 상태로 반영한다.

## 5. Upbit 실제 잔고와 전략 기록 동기화

### 문제

사용자가 Upbit 앱에서 직접 매수·매도하면 실제 코인 수량과 SignalTrade 전략별 포지션 합계가 달라진다. 외부 거래는 어느 전략의 거래인지 자동으로 알 수 없다.

### 변경

- 실제 수량과 전략 기록 수량 비교 API/UI
- `일치`, `외부 보유 수량`, `실제 잔고 부족` 상태 구분
- 사용자가 전략과 수량을 선택해 배정·차감
- 실제 Upbit 주문 없이 내부 전략 실행 기록만 조정
- `position_sync_adjustment` 감사 원장 저장
- Telegram `/sync` 명령과 전략 선택 버튼
- 버튼 클릭 시 최신 잔고 재검증

### 해결 결과

외부 거래를 임의 전략에 자동 귀속하지 않고 사용자가 의미에 맞는 전략을 선택해 기록을 맞출 수 있다.

### 검증

웹 API와 Telegram `/sync`가 정상 응답하며, 일치 상태 메시지를 확인했다.

## 6. 잔고 불일치 자동 감지

### 문제

사용자가 웹을 열거나 `/sync`를 실행하기 전까지 실제 잔고 차이를 알 수 없었다.

### 변경

- worker가 기본 60초마다 실전 사용자 잔고 비교
- 새로운 불일치만 Telegram 알림
- 동일 사건의 반복 알림 방지
- 차이 수량과 최근 확인 시각 갱신
- 다시 일치하면 사건 해결 처리
- worker 재시작 후에도 사건과 알림 이력 유지

### 해결 결과

사용자가 직접 조회하지 않아도 외부 거래나 수량 부족을 알 수 있고, 반복 알림으로 인한 피로는 방지한다.

## 7. 중복 주문과 동시 실행 방지

### 문제

같은 신호 재처리는 DB 제약으로 막을 수 있었지만, 서로 다른 신호나 버튼 요청이 거의 동시에 들어오면 둘 다 주문 전 검사를 통과할 가능성이 있었다.

### 변경

- `signal_id + user_strategy_id` DB 고유 제약 유지
- 사용자 전략 행에 PostgreSQL row lock 적용
- 실전의 `ready`, `submitted`, `partially_filled`, `uncertain`을 진행 중으로 취급
- 모의의 `simulated_pending`을 진행 중으로 취급
- 진행 중 동일 방향 주문은 추가 실행 및 Telegram 알림 없이 건너뜀

### 해결 결과

worker 재시도, 거의 동시에 발생한 전략 신호, 버튼 연속 클릭이 같은 전략의 중복 주문으로 이어지는 것을 DB 단위에서 방지한다.

## 8. worker 중단 시 미완료 주문 복구

### 문제

주문 실행 레코드를 선점한 직후 worker가 종료되면 `ready` 또는 `simulated_pending` 상태가 계속 남을 수 있다. 실전 주문은 Upbit에는 전달됐지만 DB 응답을 저장하지 못했을 수도 있어 무조건 재주문하면 위험하다.

### 변경

- 기본 2분 이상 멈춘 준비 상태 검사
- 모의 `simulated_pending`은 DB 반영 전임을 확정할 수 있어 실패 처리
- 실전 `ready`는 Upbit 실제 잔고와 전략 기록 차이 확인
- 주문 방향과 잔고 차이가 일치하면 `uncertain` 처리
- `uncertain` 주문은 추가 동일 방향 주문 차단 및 Telegram 확인 요청
- 사용자가 웹 또는 `/sync`로 차이를 반영하면 `reconciled` 처리
- 잔고 차이가 없으면 실패 상태로 정리

### 모의와 실전이 다른 이유

모의투자의 최종 상태는 모두 SignalTrade DB에 있다. DB에 반영되지 않았다면 체결되지 않은 것이 확실하다. 실전의 최종 상태는 Upbit에 있으므로 worker가 응답 저장 전에 멈추면 실제 체결 여부를 단정할 수 없다.

### 해결 결과

worker 재시작 후 미완료 기록이 영구적으로 남는 문제를 줄이고, 체결 여부가 불확실한 실전 주문을 자동 재주문해 이중 매매하는 위험을 막는다.

## 전체 검증 결과

1~8번 완료 시점 기준:

```text
backend pytest: 34 passed
frontend ESLint: passed
frontend production build: passed
strategy-worker: running
Telegram polling: running
Upbit WebSocket: connected
```

장시간 실전 운영, EC2 운영 자동화, 장애 대응 고가용성은 MVP 이후 운영 검증 범위로 남아 있다.

## 9. DB 스키마 버전 관리 전환

### 문제

MVP 기능을 빠르게 추가하는 동안 새 환경은 SQLAlchemy `create_all()`로 테이블을 만들고, 기존 DB 변경은 순서가 붙은 SQL 파일을 직접 적용했다. 초기 개발에는 단순했지만 다음 문제가 있었다.

- 어떤 DB에 어떤 변경까지 적용됐는지 자동으로 확인할 수 없음
- 팀원 로컬 DB, CI DB와 EC2 DB의 구조가 달라질 가능성
- SQL 적용 순서 누락이나 중복 실행 위험
- SQLAlchemy 모델과 실제 PostgreSQL 구조의 차이를 자동 검사하기 어려움
- 배포 전에 사람이 SQL 파일을 골라 실행해야 함

### 변경

MVP 기능과 최종 테이블 구조가 확정된 시점에 테스트 데이터가 들어 있던 PostgreSQL volume을 초기화하고 Alembic 기준으로 전체 DB를 재구성했다.

- 당시 SQLAlchemy 모델 12개를 기준으로 최초 Alembic 리비전 생성
- API와 worker의 `Base.metadata.create_all()` 제거
- 기존 수동 SQL 마이그레이션 20개와 `backend/migrations` 제거
- DB 스키마 버전을 `alembic_version` 테이블로 관리
- Compose에 일회성 `migrate` 서비스 추가
- `migrate` 성공 후에만 backend와 strategy-worker가 시작되도록 의존성 설정
- 전략 카탈로그 5개는 DB 스키마 생성 후 애플리케이션 기준 데이터로 시드
- CI에서 `alembic upgrade head`와 `alembic check` 실행

### 해결 결과

로컬, CI와 이후 EC2 환경에서 동일한 리비전을 순서대로 적용할 수 있게 됐다. 모델 변경이 DB 리비전에 반영되지 않으면 CI의 `alembic check`가 감지하며, 배포 시 별도의 수동 SQL 선택 없이 `alembic upgrade head`로 최신 구조를 구성한다.

### 검증

```text
빈 PostgreSQL에서 최초 revision upgrade: passed
downgrade base → upgrade head 왕복: passed
SQLAlchemy 모델과 DB 구조 비교: no new upgrade operations
당시 서비스 테이블: 12개
전략 기준 데이터: 5개
사용자·거래 테스트 데이터: 초기화
backend pytest: 34 passed
frontend ESLint/build: passed
```

## 10. 전략 공식과 지원 종목 분리

### 문제

초기 MVP는 `strategy.market`에 `KRW-BTC`를 저장해 전략 공식과 종목이 한 행에 묶여 있었다. 종목을 늘릴 때 전략 행이나 전용 컬럼을 반복해서 추가하면 동일한 계산 공식이 중복되고, 사용자 설정과 포지션이 어느 종목에 속하는지 확장하기 어려웠다.

### 변경

- `supported_market` 테이블을 추가하고 6개 KRW 마켓을 기준 데이터로 저장
- `strategy`에서 종목을 제거해 SMA, RSI 등 계산 공식만 관리
- `user_strategy.market_id`를 추가해 사용자·모드·종목·전략 조합을 한 행으로 저장
- 기존 BTC 구독은 Alembic 마이그레이션에서 `KRW-BTC` 행에 연결
- `strategy_runtime`과 `strategy_signal`의 고유 제약에 종목을 포함
- WebSocket 구독, 분봉 계산, 신호 분배, 손절·익절, 포지션과 잔고 동기화를 종목별로 분리
- 프론트엔드에 종목 선택기를 추가하고 모든 종목의 투자 비율 합계를 모드별 100%로 제한
- Telegram 전략 명령을 `/paper_btc_sma`, `/live_eth_rsi`처럼 모드·종목·전략 조합으로 구분

지원 종목은 `BTC, ETH, XRP, SOL, DOGE, TRX`이다. 24시간 거래대금 순위에 따라 자동 교체하지 않고 고정 카탈로그로 관리해 기존 설정과 포지션의 연결을 보호한다. ADA, AVAX, LINK, DOT는 지원 목록에서 제외하되 과거 기록 보존을 위해 DB에서 비활성화한다.

### 해결 결과

종목이나 전략이 추가돼도 DB 컬럼을 만들 필요 없이 `supported_market`과 `user_strategy` 행을 추가할 수 있다. 동일한 전략을 BTC와 ETH에 서로 다른 분봉·투자 비율·손절·익절 값으로 독립 적용할 수 있으며, 체결 기록과 포지션도 조합별로 분리된다.

### 검증

```text
Alembic upgrade: 8f3c6d1a2b40 → 4b9d7e2f1a60 passed
기존 사용자 구독의 KRW-BTC 연결: passed
지원 종목 기준 데이터: 6개
동일 전략의 BTC/ETH 독립 설정: passed
Upbit WebSocket 6종목 연결: passed
backend pytest: 49 passed
frontend ESLint/build: passed
```
