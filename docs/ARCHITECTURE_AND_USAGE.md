# SignalTrade 프로젝트 구조와 데이터 흐름

## 1. 전체 구조

SignalTrade는 웹 요청을 처리하는 Backend와 계속 실행되는 자동매매 Worker를 분리합니다. PostgreSQL은 업무 데이터의 원본이며, 관측 데이터는 Loki와 Prometheus에 별도로 저장합니다.

```text
브라우저 ── HTTPS ── Nginx/React ── /api ── FastAPI Backend ── PostgreSQL
                         │                         ▲                 ▲
                         │ /monitoring             │                 │
                         ▼                         └── strategy-worker┘
                       Grafana                           │
                                            Upbit REST/WS · Telegram

JSON stdout ── Docker local log ── Alloy ── Loki ───────┐
App/Worker/exporter metrics ───── Prometheus ───────────┴── Grafana
```

## 2. 컨테이너 구성

### 애플리케이션

| 서비스 | 역할 |
|---|---|
| `frontend` | React 정적 파일, API·Grafana reverse proxy, TLS |
| `backend` | 인증, 사용자 설정, 전략·포지션·분석 API |
| `strategy-worker` | 시세 수신, 전략 평가, 주문, 정합성, 복구, Telegram |
| `migrate` | 시작 전 Alembic migration을 실행하고 종료 |
| `db` | PostgreSQL 업무 데이터 |

Backend, Worker, migrate는 같은 Backend 이미지를 사용하지만 명령과 수명 주기가 다릅니다.

### 모니터링

| 서비스 | 역할 |
|---|---|
| `alloy` | Docker 로그 수집·가공·전송 |
| `loki` | 로그 저장과 LogQL 조회 |
| `prometheus` | 애플리케이션·인프라 메트릭 수집 |
| `grafana` | 로그와 메트릭 시각화 |
| `node-exporter` | EC2 호스트 CPU·메모리·디스크 |
| `cadvisor` | 컨테이너 CPU·메모리 |
| `postgres-exporter` | PostgreSQL 상태와 통계 |

두 Compose 프로젝트는 외부 Docker 네트워크 `signaltrade-observability`로 연결됩니다.

## 3. 코드 구조

```text
.
├── backend/
│   ├── app/api/            # HTTP endpoint
│   ├── app/core/           # 설정, DB, 보안, 로그, 메트릭
│   ├── app/models/         # DB model
│   ├── app/schemas/        # API schema
│   ├── app/services/       # 도메인과 외부 연동
│   ├── app/workers/        # Worker runtime
│   ├── alembic/            # migration
│   └── tests/
├── frontend/
│   ├── src/api/            # API client
│   ├── src/components/     # 공통 UI
│   ├── src/pages/          # route별 화면
│   └── nginx/              # 운영 reverse proxy
├── monitoring/             # Alloy, Loki, Prometheus, Grafana 설정
├── scripts/                # 운영 배포·검증 script
├── .github/workflows/      # CI, release, deploy workflow
├── docker-compose.yml
└── docker-compose.production.yml
```

## 4. 주요 데이터 흐름

### 인증과 보안

```text
회원가입/로그인
→ Backend 검증
→ 비밀번호 hash와 인증 상태 저장
→ Access Token 발급
→ 보호 API에 Bearer Token 전달
```

로그인 실패, 잠금, API Key와 Telegram 변경은 보안 감사 대상으로 기록합니다. Upbit Key는 검증 후 암호화해 저장하며 로그에는 원문을 남기지 않습니다.

### 카탈로그와 사용자 전략

```text
Backend 카탈로그 정의
→ DB seed와 활성 상태
→ Frontend가 활성 마켓·전략 조회
→ 사용자가 모드·마켓·전략·분봉·비율 설정
→ Worker가 활성 사용자 설정 refresh
```

마켓과 전략 수는 고정 계약이 아닙니다. 항목을 비활성화해도 과거 주문과 포지션 참조가 유지되도록 기록을 삭제하지 않습니다.

투자 비율은 현금을 미리 분리하는 값이 아니라 전체 운용자산 중 해당 전략이 사용할 수 있는 최대 한도입니다. 실제 주문은 가용 현금, 기존 포지션, 수수료, 주문 최소 금액 등 추가 조건을 통과해야 합니다.

### 자동매매

```text
Upbit WebSocket 체결 수신
→ 마켓별 분봉 생성
→ 활성 전략 지표 계산
→ 마감 봉에서 신호 확정
→ 신호·실행 기록
→ 사용자별 주문 사전 검사
→ 모의계좌 반영 또는 Upbit 주문
→ 주문·거래·포지션 기록
→ 필요 시 Telegram 알림
```

같은 전략 공식을 여러 사용자가 사용해도 사용자별 설정과 자산 상태는 별도입니다. 계산 가능한 공통 시장 데이터는 공유하지만 다른 사용자의 주문 결과나 포지션을 재사용하지 않습니다.

### 포지션 정합성과 복구

Worker는 주문 상태 확인, 포지션 불일치 검사, 중단 주문 복구를 서로 다른 주기로 수행합니다.

```text
Upbit 실제 주문·잔고 ↔ 내부 주문·실행·전략 포지션
                            │
                    불일치 감지·조정 기록
```

사용자가 Upbit에서 직접 거래하면 차이가 발생할 수 있습니다. 동기화 작업은 내부 전략 귀속을 조정하며 실제 주문 여부와 감사 기록을 명확히 구분합니다.

### Telegram

```text
Telegram getUpdates long polling
→ 명령/연동 코드 검증
→ 사용자 연결 또는 명령 실행
→ 결과 응답과 운영 로그
```

같은 Bot Token으로 polling하는 인스턴스는 하나여야 합니다. 둘 이상이면 Telegram이 409 Conflict를 반환합니다.

### 로그와 메트릭

```text
요청/Worker event → JSON stdout → Docker 회전 로그 → Alloy → Loki
요청/외부 호출/DB/Worker 상태 → /metrics → Prometheus → Grafana
```

로그는 개별 사건과 원인 추적에, 메트릭은 추세·비율·지연·상태 파악에 사용합니다. 고빈도 정상 상태를 모두 INFO 로그로 남기기보다 counter, histogram, last-success metric으로 표현합니다.

## 5. 저장소와 수명

| 데이터 | 저장 위치 |
|---|---|
| 업무 데이터 | PostgreSQL `postgres_data` volume |
| 컨테이너 1차 로그 | Docker `local` logging driver |
| 조회용 로그 | Loki volume |
| 시계열 메트릭 | Prometheus volume |
| Grafana 사용자 설정 | Grafana volume |

Compose 재배포와 일반 `down`은 named volume을 유지합니다. `down -v`, volume 삭제, EC2 디스크 유실은 별개이므로 운영 백업 정책이 필요합니다.

## 6. 사용자 흐름

1. 회원가입하고 로그인합니다.
2. 설정에서 Upbit API Key와 Telegram을 연결합니다.
3. 통합 홈에서 모의·실전 상태를 확인합니다.
4. 투자 모드에서 활성 마켓과 전략을 선택하고 비율·분봉을 설정합니다.
5. 모의투자로 동작을 검증한 뒤 필요할 때 실전투자를 활성화합니다.
6. 포지션, 주문, 거래, 분석 화면에서 결과를 확인합니다.
7. 운영자는 Grafana에서 API, Worker, DB, 로그, 호스트·컨테이너 상태를 함께 확인합니다.

실행 방법은 [../SETUP.md](../SETUP.md), 관측성 상세는 [OBSERVABILITY.md](OBSERVABILITY.md)를 참고합니다.
