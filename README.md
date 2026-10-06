# SignalTrade

SignalTrade는 Upbit 시세를 바탕으로 투자 전략을 평가하고, 모의투자 또는 실전 주문을 실행하는 자동매매 웹 서비스입니다.

현재 운영 구조는 도메인별 API 4개와 Worker 5개로 분리된 MSA이며, AWS EKS에서 실행됩니다. 서비스 이미지는 독립 저장소의 CI에서 검증·빌드하고, 배포할 Git SHA는 GitOps 저장소에서 관리합니다.

> 이 저장소는 초기 통합형 애플리케이션과 Docker Compose 기반 로컬 실행 환경을 보존합니다. 현재 MSA 서비스와 EKS 배포 선언은 아래의 조직 저장소에서 관리합니다.

## 주요 기능

- JWT 인증, 로그인 실패 제한과 Telegram 기반 비밀번호 재설정
- Upbit API Key 검증 및 암호화 저장
- 사용자별 전략·마켓·투자 비율·손절·익절 설정
- Upbit REST·WebSocket 시세를 이용한 전략 신호 생성
- 모의투자와 실전 주문, 체결·수수료·거래 원장 관리
- 포지션·실제 잔고 비교와 불일치 조정
- 실현손익, 승률, 자산·종목별 분석
- Telegram 주문·체결·오류 알림

## 현재 운영 아키텍처

```text
사용자
  │ HTTPS
  ▼
CloudFront ── 정적 파일 ── 비공개 S3
  │ /api
  ▼
AWS ALB Ingress
  ├─ /auth, /users                 → Identity API
  ├─ /strategies                   → Strategy API
  ├─ /paper-account, /trades       → Trading API
  └─ /positions, /analytics        → Portfolio API

Strategy Worker ── signal + outbox ──┐
Identity / Trading / Portfolio ──────┼─→ Messaging Worker
                                      │        │
                                      │        ▼
                                      │      Amazon SQS
                                      │        ├─ Trading Worker
                                      │        ├─ Strategy Worker
                                      │        └─ Notification Worker ── Telegram
                                      ▼
                                Amazon RDS PostgreSQL

Portfolio Worker ── 실제 잔고·포지션 정합성 점검 ── Upbit / RDS

Redis                    만료형 보안 상태·알림 중복 방지
AWS Secrets Manager      서비스 비밀값
External Secrets         Kubernetes Secret 동기화
Prometheus · Loki        메트릭·로그 수집
Grafana                  서비스·Kubernetes·DB·보안·부하테스트 관측
```

### 서비스 경계

| 서비스 | 책임 | 쓰기 권한의 중심 |
|---|---|---|
| Identity | 계정, 인증, Upbit Key, Telegram 연결 | 사용자·API Key·보안 감사 |
| Strategy | 전략 설정, 시세 처리, 매수·매도 신호 생성 | 전략·런타임·신호 |
| Trading | 모의·실전 주문, 체결, 거래 원장 | 실행 요청·체결·모의계좌 |
| Portfolio | 자산·손익 조회, 실제 잔고 비교와 정합성 조정 | 불일치·조정 이력 |
| Messaging | Outbox 이벤트 조회와 SQS 발행 | Outbox 발행 상태 |
| Notification | Telegram 알림과 명령 처리 | 영속 도메인 테이블 없음 |

각 서비스는 자신의 도메인 데이터만 변경합니다. 다른 서비스의 결과가 필요하면 내부 HTTP API로 조회하고, 비동기 처리는 Outbox와 SQS를 사용합니다.

## 이벤트 전달

업무 데이터와 메시지 발행을 따로 처리할 때 생길 수 있는 유실을 줄이기 위해 Transactional Outbox를 사용합니다.

```text
업무 데이터 + message_outbox를 하나의 DB transaction으로 저장
  → Messaging Worker가 미발행 이벤트 조회
  → 이벤트 종류에 따라 SQS Queue 선택
  → 대상 Worker 처리
  → 발행 완료 기록 또는 재시도
```

| Queue | 주요 이벤트 | 소비자 |
|---|---|---|
| Trading Queue | 전략 신호, 포지션 조정, 수동 청산 | Trading Worker |
| Strategy Queue | 전략 예산 변경 | Strategy Worker |
| Notification Queue | 사용자 알림 요청 | Notification Worker |

SQS의 at-least-once 전달을 고려해 소비자는 중복 처리를 방지합니다. Notification은 Redis의 짧은 잠금과 완료 표시를 이용합니다.

## 저장소 구성

| 저장소 | 역할 |
|---|---|
| [`signaltrade-core`](https://github.com/KTCloud-Crypto/signaltrade-core) | 공통 DB migration, 메시지 계약, 로컬 kind, AWS CloudFormation 인프라 |
| [`signaltrade-identity`](https://github.com/KTCloud-Crypto/signaltrade-identity) | 인증·사용자·Upbit Key·Telegram 연결 |
| [`signaltrade-strategy`](https://github.com/KTCloud-Crypto/signaltrade-strategy) | 전략 API와 신호 생성 Worker |
| [`signaltrade-trading`](https://github.com/KTCloud-Crypto/signaltrade-trading) | 거래 API와 주문 실행 Worker |
| [`signaltrade-portfolio`](https://github.com/KTCloud-Crypto/signaltrade-portfolio) | 자산·포지션·손익 API와 정합성 Worker |
| [`signaltrade-messaging`](https://github.com/KTCloud-Crypto/signaltrade-messaging) | Transactional Outbox Publisher |
| [`signaltrade-notification`](https://github.com/KTCloud-Crypto/signaltrade-notification) | Telegram 알림·명령 Worker |
| [`signaltrade-frontend`](https://github.com/KTCloud-Crypto/signaltrade-frontend) | React/Vite 웹 애플리케이션 |
| [`signaltrade-gitops`](https://github.com/KTCloud-Crypto/signaltrade-gitops) | Helm, 환경별 이미지 tag, Argo CD, 모니터링 배포 선언 |
| [`KTCloud-Crypto`](https://github.com/KTCloud-Crypto/KTCloud-Crypto) | 초기 통합형 구현, Docker Compose, 부하테스트 시나리오 |

## 기술 스택

| 영역 | 기술 |
|---|---|
| Frontend | React, Vite, Nginx, Amazon S3, CloudFront |
| API | Python, FastAPI, Uvicorn, SQLAlchemy, Alembic |
| Worker | Python asyncio, Upbit REST/WebSocket, Telegram Bot API |
| Data | Amazon RDS for PostgreSQL, ElastiCache for Redis |
| Messaging | Transactional Outbox, Amazon SQS, DLQ |
| Runtime | Docker, Amazon EKS, Kubernetes, Helm |
| Network | VPC, ALB Ingress, CloudFront, Private Subnet, NAT Gateway |
| Secrets | AWS Secrets Manager, External Secrets, EKS Pod Identity |
| Observability | Prometheus, Grafana, Loki, Grafana Alloy, kube-state-metrics, node-exporter |
| CI/CD | GitHub Actions, Amazon ECR, Git SHA image, Argo CD |
| Infrastructure | AWS CloudFormation, GitOps |

## 배포 흐름

서비스 코드와 배포 상태를 서로 다른 저장소에서 관리합니다.

```text
서비스 저장소
  → 테스트·lint·migration 검증·이미지 취약점 검사
  → Amazon ECR에 immutable Git SHA image push
  → signaltrade-gitops repository_dispatch
  → 환경별 Helm values의 image tag 갱신
  → Argo CD가 변경 감지·자동 동기화
  → EKS Deployment·Service·Ingress 반영
```

- API는 `RollingUpdate`로 교체하며 `maxUnavailable: 0`, `maxSurge: 1`을 사용합니다.
- API마다 startup·readiness·liveness probe와 PodDisruptionBudget을 둡니다.
- staging API는 HPA로 최소 2개, 최대 5개 Pod까지 확장하며 CPU 70%를 기준으로 사용합니다.
- Worker는 중복 동시 실행을 줄이기 위해 독립 Deployment와 `Recreate` 전략을 사용합니다.
- DB migration은 애플리케이션과 분리된 Kubernetes Job으로 실행합니다.
- Argo CD는 staging 배포의 자동 동기화와 self-heal을 수행합니다.

배포 선언은 [`signaltrade-gitops`](https://github.com/KTCloud-Crypto/signaltrade-gitops), AWS 기반 인프라는 [`signaltrade-core`](https://github.com/KTCloud-Crypto/signaltrade-core)에서 관리합니다.

## 보안과 접근 제어

- 브라우저는 ALB의 경로 규칙을 통해 담당 API에 접근합니다.
- NetworkPolicy는 기본 통신을 차단하고 필요한 서비스·DB·Redis·DNS·외부 통신만 허용합니다.
- 민감정보는 AWS Secrets Manager에 저장하고 External Secrets로 동기화합니다.
- 서비스별 ServiceAccount와 EKS Pod Identity로 AWS 접근 권한을 분리합니다.
- Upbit Secret Key는 암호화해 저장하며 필요한 내부 요청에서만 복호화합니다.
- Token, 거래소 Key, Authorization 값은 애플리케이션 로그에 기록하지 않습니다.
- CloudFront·ALB 접근 로그를 수집해 보안 운영 대시보드에서 401·403, 의심 경로와 원천 IP를 확인합니다.

## 관측성

Prometheus는 Kubernetes API를 통해 API·Worker Pod를 발견하고 애플리케이션 메트릭을 수집합니다. kube-state-metrics와 node-exporter, kubelet cAdvisor, PostgreSQL exporter를 함께 사용해 서비스·Pod·노드·DB 상태를 같은 시간대에서 비교합니다.

Loki와 Alloy는 구조화된 애플리케이션 로그를 수집합니다. 요청 로그에는 `request_id`, 서비스, 환경, 경로, 상태 코드와 처리시간을 포함해 메트릭과 오류 로그를 연결합니다.

### Grafana 대시보드

| 대시보드 | 확인 내용 |
|---|---|
| SignalTrade 메인 요약 | 서비스 상태, 사용자 영향, Worker와 주요 오류 |
| SignalTrade 서비스 개요 | API·Worker 상태와 마지막 성공 시각 |
| SignalTrade API 트래픽 | 경로별 RPS, 상태 코드, p95와 외부 요청 지연 |
| SignalTrade PostgreSQL 모니터링 | 연결, 트랜잭션, 교착, 저장 공간과 캐시 |
| SignalTrade Kubernetes 클러스터 | Deployment·Pod·HPA·노드 상태와 자원 사용량 |
| SignalTrade 운영 모니터링 | 인프라·로그 파이프라인 운영 상태 |
| SignalTrade 보안 운영 | CloudFront·ALB 접근 로그와 보안 이벤트 |
| SignalTrade 부하 테스트 | k6, Backend, Pod, DB Pool과 외부 API 지표 비교 |

대시보드와 Prometheus·Loki 배포 선언은 `signaltrade-gitops/addons/monitoring`에서 함께 버전 관리합니다.

## 부하 테스트

실제 사용자가 로그인한 뒤 대시보드와 모의투자 화면을 조회하는 흐름을 k6로 재현합니다.

```text
로그인
  → 사용자·마켓·시세 확인
  → 모의계좌·전략 조회
  → 계좌·전략·포지션·분석·원장·실행 내역을 비율에 따라 반복 조회
```

### VU 기반 테스트

| 단계 | 전체 부하 | 부하 발생기당 | 시간 | 요청 구성 |
|---|---:|---:|---:|---|
| 인증 확인 | 10 VU | 5 VU | 2분 | 읽기 전용 |
| 읽기 일반 부하 | 50 VU | 25 VU | 5분 | 읽기 전용 |
| 읽기 목표 부하 | 100 VU | 50 VU | 10분 | 읽기 전용 |
| 혼합 테스트 부하 | 20 VU | 10 VU | 3분 | 읽기 90%·쓰기 10% |
| 혼합 일반 부하 | 50 VU | 25 VU | 5분 | 읽기 90%·쓰기 10% |
| 혼합 목표 부하 | 100 VU | 50 VU | 10분 | 읽기 90%·쓰기 10% |
| 쓰기 검증 | 10 VU | 5 VU | 2분 | 쓰기 비율 40% |
| 쓰기 테스트 | 20 VU | 10 VU | 3분 | 쓰기 비율 40% |
| 쓰기 일반 부하 | 50 VU | 25 VU | 5분 | 쓰기 비율 40% |

단계 사이에는 5분의 휴식 시간을 두고 응답시간, 오류, Pending Pod, DB 연결과 Worker 상태의 회복을 확인합니다.

초기 단일 EC2 환경에서는 읽기 전용·혼합·쓰기 집중·고정 RPS 시나리오를 수행했습니다. MSA 전환 후 EKS 환경에서는 시간과 비용을 고려해 동일한 읽기 전용 시나리오만 재실행했습니다. 원본 측정 결과를 보존하지 않았으므로 수치 비교 결과는 기재하지 않고, 재현 가능한 시나리오와 관측 기준만 관리합니다.

### 고정 RPS 테스트

고정 도착률 테스트는 동시 사용자 수와 별도로 서버가 일정 RPS를 안정적으로 처리하는지 확인합니다. 목표 RPS 유지 여부, p95·p99, 오류율과 `dropped_iterations` 발생 시점을 관측합니다.

Grafana 부하테스트 대시보드는 `test_run_id`, `scenario`, `runner_id`, `stage` 태그를 기준으로 결과를 구분합니다. Prometheus Remote Write로 여러 실행기의 결과를 전송할 때는 같은 `test_run_id`와 서로 다른 `runner_id`를 지정합니다. 자세한 실행 방법은 [`load-tests/README.md`](load-tests/README.md)와 [GitOps 모니터링 구성](https://github.com/KTCloud-Crypto/signaltrade-gitops/tree/develop/addons/monitoring)을 참고하세요.

## 로컬 실행

이 저장소의 Docker Compose는 초기 통합형 애플리케이션을 로컬에서 확인할 때 사용합니다. 현재 MSA 전체 실행은 `signaltrade-core`의 kind 환경과 `signaltrade-gitops`의 배포 선언을 기준으로 합니다.

### 통합형 Docker Compose

```bash
cp .env.example .env
cp monitoring/.env.example monitoring/.env

docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  up -d

docker compose up -d --build
docker compose ps
```

| 대상 | 주소 |
|---|---|
| Web UI | <http://localhost> |
| Backend health | <http://localhost:8000/health> |
| Swagger UI | <http://localhost:8000/docs> |
| Grafana | <http://localhost:3000> |

환경 변수와 모니터링 계정 설정은 [설치 및 실행 방법](SETUP.md), [관측성 운영 문서](docs/OBSERVABILITY.md)를 참고하세요.

## 문서

- [부하 테스트 실행](load-tests/README.md)
- [프로젝트 구조와 데이터 흐름](docs/ARCHITECTURE_AND_USAGE.md)
- [로그 및 모니터링 운영](docs/OBSERVABILITY.md)
- [초기 통합형 CI/CD](docs/CD_SETUP.md)
- [MVP 안정화 기록](docs/MVP_STABILIZATION.md)
- [GitOps 운영](https://github.com/KTCloud-Crypto/signaltrade-gitops)
- [AWS·로컬 Kubernetes 인프라](https://github.com/KTCloud-Crypto/signaltrade-core)

## 주의 사항

자동매매와 실전 주문은 자산 손실 위험이 있습니다. Upbit API Key에는 출금 권한을 부여하지 않고 필요한 최소 권한만 사용하세요. 모의투자와 충분한 검증을 거친 뒤 사용자별 실전투자 설정을 활성화해야 합니다. 이 프로젝트의 전략과 결과는 수익을 보장하지 않습니다.
