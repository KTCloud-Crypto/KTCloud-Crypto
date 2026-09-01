# SignalTrade MSA migration plan

이 문서는 `feat/132`에서 기존 기능을 빠뜨리지 않고 프로세스를 분리하기 위한 기준 문서다.
서비스 이름보다 **데이터 변경 권한과 장애 경계**를 우선한다.

## 안전 원칙

- 실전 주문 경로는 모의 주문과 중복 방지 테스트가 통과하기 전까지 전환하지 않는다.
- 하나의 도메인 데이터를 변경하는 서비스는 하나만 둔다.
- 서비스 간 비동기 작업은 내구성 있는 Queue와 idempotency key를 사용한다.
- DB 기록과 메시지 발행의 불일치는 transactional outbox로 방지한다.
- 초기에는 PostgreSQL을 공유하되, 소유하지 않은 테이블을 다른 서비스가 직접 변경하지 않는다.
- Market Data와 Strategy는 `python -m app.strategy.worker`에서 하나의 런타임으로 실행한다.

## 최종 논리 서비스

| 서비스 | 책임 | 소유 데이터 |
|---|---|---|
| API Gateway | 외부 요청 라우팅, 인증 확인, rate limit, request ID | 없음 |
| Identity & Exchange Connection | 사용자 인증, 프로필, Upbit API Key, Telegram 연결, 보안 감사 | `user`, `api_key`, `security_audit_log` |
| Market Data | Upbit WebSocket, 체결 수신, 캔들 생성·검증, 최신 가격 | 영속 원장 없음; 최신 가격 cache |
| Strategy | 전략 카탈로그·구독 설정, 지표 계산, runtime, 신호 생성, 손절·익절 판정 | `strategy`, `supported_market`, `user_strategy`, `strategy_runtime`, `strategy_signal`, 구독 이력 |
| Trading | 사용자별 신호 분배, 주문 preflight, 실전·모의 체결, 미체결 확인, 실행 복구 | `strategy_execution`, `trade`, `paper_account`, `paper_ledger` |
| Portfolio & Reconciliation | 전략 포지션 projection, 계좌 잔고, 미배정, shortfall, deduct, 손익 조회 | `position_sync_adjustment`, `position_mismatch_incident`; execution/trade는 읽기 전용 |
| Notification & Bot Gateway | Telegram 명령 수신, 사용자 알림, 재시도와 발송 이력 | 향후 notification delivery 원장 |

## 코드 디렉터리 경계

논리 서비스의 책임은 실행 프로세스뿐 아니라 코드 경로에서도 드러나야 한다. 다만
초기에는 하나의 저장소와 하나의 `backend/app` 패키지를 유지하는 **모듈형 모놀리스**로
정리하고, 각 모듈이 독립 배포·독립 데이터 저장소를 실제로 필요로 할 때 별도 저장소를
검토한다.

```text
backend/app/
├── api/           # HTTP transport만 담당, 도메인 로직을 직접 구현하지 않음
├── identity/      # 사용자·인증·거래소 연결
├── market_data/   # 시세·캔들·WebSocket
├── strategy/      # 전략 설정·평가·신호 생성
├── trading/       # 주문·체결·미체결 확인·실행 복구
├── portfolio/     # 포지션·잔고 정합성·deduct
├── notification/  # Telegram 입력·알림 발송
├── messaging/     # Outbox·SQS·Redis 등 서비스 간 공통 기반
└── core/          # DB·설정·관측성 등 공통 기반
```

파일은 복사하지 않고 책임 서비스의 디렉터리로 이동한다. `trading/`에는 기존 주문 코드와
Trading worker를, `strategy/`에는 전략 카탈로그·엔진·평가기·예산 배정·손절/익절 판정을
이동했다. `portfolio/`에는 전략 포지션 projection, 실제 잔고 정합성 비교, shortfall 감시와
deduct 처리를, `notification/`에는 Telegram 알림 전송과 명령 polling 처리를 이동했다.
이후 `market_data/`, `identity/` 순서로 이동한다.
모델과 schema는 공유 DB
전환 기간에는 기존 `models/`, `schemas/`에 유지하되, 각 서비스의 쓰기 권한은 위 표를
따른다.

## 현재 Worker 작업의 이동 대상

| 현재 작업 | 현재 위치 | 최종 책임 |
|---|---|---|
| Upbit 체결 WebSocket | `UpbitTradeStream` | Market Data |
| 체결량·최신가 모니터링 | `MarketStreamMonitor` | Market Data |
| 캔들 생성·공식 캔들 검증 | `StrategyEngine` | Market Data |
| 활성 전략 주기적 조회 | `StrategyEngine.refresh_loop` | Strategy |
| SMA·RSI·볼린저 등 평가 | `StrategyEngine` | Strategy |
| StrategyRuntime·Signal 기록 | `StrategyEngine` | Strategy |
| 손절·익절 감시 | `risk_exit` | Strategy |
| 신호 대상 사용자 조회 | `signal_dispatcher` | Trading |
| 주문 전 잔고·예산·포지션 검사 | `execution_preflight`, `signal_dispatcher` | Trading |
| 실전 Upbit 주문 | `live_order`, `signal_dispatcher` | Trading |
| 모의 체결·현금 원장 | `paper_trading`, `signal_dispatcher` | Trading |
| 미체결·부분 체결 조회 | `order_reconciliation` | Trading |
| 오래 멈춘 실행 복구 | `execution_recovery` | Trading |
| 실제 잔고와 전략 기록 비교 | `position_monitor`, `position_reconciliation` | Portfolio |
| 전략 포지션·평균원가 계산 | `strategy_positions` | Portfolio |
| deduct 적용 | Positions API, `position_deduction` | Portfolio |
| Telegram long polling | `telegram_poller` | Notification |
| 주문·보안·shortfall 알림 | 여러 서비스의 Telegram 호출 | Notification |

## 서비스 간 메시지

### Command: 한 소비자가 반드시 처리할 작업

- `ExecuteStrategySignal`: 전략 신호를 사용자별 주문으로 처리한다.
- `ExecuteManualSell`: 웹·Telegram 수동 매도를 처리한다.
- `ApplyPositionDeduction`: 검증된 shortfall 차감을 적용한다.
- `SendNotification`: 사용자 알림을 발송한다.

### Event: 이미 발생한 사실을 필요한 소비자에게 알림

- `CandleClosed`
- `StrategySignalCreated`
- `OrderSubmitted`
- `TradeExecuted`
- `OrderFailed`
- `ShortfallDetected`
- `PositionDeducted`

모든 메시지는 최소한 `message_id`, `message_type`, `occurred_at`, `correlation_id`,
`producer`, `schema_version`, `payload`를 가진다. 주문 Command는
`signal_id + user_strategy_id + side`를 기반으로 한 idempotency key를 추가한다.

## 1차 로컬 배포 단위

논리 서비스 일곱 개를 처음부터 모두 별도 컨테이너로 만들지는 않는다.

1. `api`: API Gateway 뒤의 FastAPI와 Identity API
2. `market-strategy`: 시세 수집과 전략 신호 생성
3. `trading`: 실전·모의 주문, 미체결 확인, 실행 복구
4. `portfolio`: 포지션 projection과 정합성 감시
5. `notification`: Telegram 입력과 알림 출력

PostgreSQL은 공유하고 Queue는 별도 컨테이너로 둔다. Redis는 최신가 cache와
짧은 수명의 lock에만 사용하며, 주문 Command의 유일한 저장소로 사용하지 않는다.

## 단계별 전환

1. 현재 통합 테스트를 기준선으로 고정한다.
2. 메시지 envelope, Queue adapter, outbox 저장소를 추가하되 기존 실행 경로는 유지한다.
3. `StrategySignalCreated`를 outbox에 함께 저장하고 메시지 전달·중복 방지 경로를 검증한다. (완료)
4. 신호 실행 권한을 Trading으로 이전하고 기존 직접 `dispatch_signal` 호출을 제거한다. (완료)
5. 미체결 확인과 실행 복구를 Trading 프로세스로 이동한다. (완료)
6. 정합성 감시와 deduct를 Portfolio 프로세스로 이동한다.
7. Telegram 입력·출력을 Notification 프로세스로 이동한다.
8. 기존 통합 Worker를 제거하고 Compose 장애·재시도·중복 메시지 테스트를 수행한다.

### 로컬 인프라 선택

- Queue는 LocalStack의 SQS를 사용하고 운영에서는 AWS SQS로 교체한다.
- `signaltrade-trading-commands`는 주문 Command를 받을 Queue다.
- 5회 처리에 실패한 메시지는 `signaltrade-trading-commands-dlq`로 이동한다.
- Redis는 최신 가격 cache와 짧은 수명의 분산 lock에만 사용한다.
- PostgreSQL은 사용자·주문·체결·포지션 원장의 source of truth로 유지한다.
- 이 인프라를 기존 주문 경로에 연결하기 전까지 자동매매 동작은 변경하지 않는다.

### Transactional outbox 규칙

- 도메인 기록과 `message_outbox` 추가는 반드시 같은 DB transaction에서 처리한다.
- 발행기는 `pending` 행을 잠근 뒤 SQS로 전송하고 성공한 행을 `published`로 변경한다.
- 일시적인 SQS 오류는 지수 backoff로 재시도하며 오류 내용과 시도 횟수를 원장에 남긴다.
- SQS 전송 성공 후 DB commit이 실패하면 메시지가 다시 전송될 수 있으므로 전달 방식은
  at-least-once다. 소비자는 `message_id` 또는 `idempotency_key`로 중복 처리를 막는다.
- Outbox는 메시지 전달 원장일 뿐 주문·체결·포지션의 source of truth가 아니다.

### 현재 Trading 실행 범위

- `outbox-publisher`가 커밋된 `StrategySignalCreated`를 SQS로 발행한다.
- `trading-worker` consumer가 신호를 받아 모의·실전 주문과 `StrategyExecution` 생성을 담당한다.
- 전략 Worker, Web API, Telegram 입력 경로는 신호와 Outbox만 같은 transaction에 저장하며 주문을 직접 실행하지 않는다.
- 특정 사용자용 테스트·수동 매도·손절 신호는 `target_user_id`, `target_mode`를 보존한다.
- 같은 메시지가 재전달되어도 `(signal_id, user_strategy_id)` 유일 제약으로 주문을 중복 생성하지 않는다.
- 처리가 성공한 메시지만 ACK하며 실패하면 재시도 후 DLQ로 이동한다.
- Trading 프로세스는 5초마다 미체결 주문을 확인하고, 30초마다 중단 중 남은 준비 상태 실행을 복구한다.

## 완료 조건

- 기존 실전·모의 포지션과 손익 결과가 변하지 않는다.
- 동일 Command를 두 번 전달해도 Execution과 주문은 하나만 생성된다.
- Trading 중단 중 생성된 신호가 재시작 후 처리된다.
- Notification 중단이 주문 처리를 막지 않는다.
- Market Data 또는 Strategy replica가 늘어도 같은 신호가 중복 생성되지 않는다.
- 각 서비스가 소유한 테이블만 변경한다.
- 전체 Backend 테스트와 Compose 기반 모의투자 핵심 시나리오가 통과한다.
