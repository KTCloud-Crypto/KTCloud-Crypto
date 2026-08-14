# 로그 및 모니터링 운영

SignalTrade 관측성은 사건을 설명하는 로그와 상태 변화를 보여주는 메트릭을 함께 사용합니다. 알림 규칙은 이 저장소의 기본 범위에 포함하지 않습니다.

## 1. 수집 흐름

```text
Backend/Worker/Nginx JSON stdout
→ Docker local logging driver
→ Grafana Alloy
→ Loki
→ Grafana 로그 패널·Explore

Backend :8000/metrics · Worker :9101/metrics
node-exporter · cAdvisor · postgres-exporter
→ Prometheus
→ Grafana 메트릭 패널
```

stdout은 컨테이너가 아니라 프로세스의 표준 출력 통로입니다. Docker가 이 출력을 1차 로그 파일로 받아 관리합니다.

## 2. 수집하는 로그

| 종류 | 예시 | 목적 |
|---|---|---|
| Access/요청 | method, route, status, duration, client IP | 트래픽·지연·오류 추적 |
| 오류·예외 | exception, 실패한 작업, request ID | 장애 원인 분석 |
| 애플리케이션 | 주문 상태 변화, 복구 결과, 외부 연동 | 비즈니스 흐름 추적 |
| 사용자·보안 | 로그인 실패, 잠금, 민감 설정 변경 | 감사와 침해 대응 |
| Worker | 작업 실패·복구·상태 변화 | 백그라운드 작업 운영 |

프로덕션 기본 레벨은 INFO입니다. 반복되는 정상 polling과 계산 결과는 가능한 한 메트릭으로 표현하고, 상태 변화·실패·복구에 로그를 집중합니다. 비밀번호, 인증 Token, Upbit Key, Telegram Token은 저장하지 않으며 민감 query string과 header도 노출하지 않습니다.

## 3. 로그 형식

대표 HTTP 완료 로그는 다음 필드를 가집니다.

```json
{
  "timestamp": "2026-08-14T00:00:00+00:00",
  "level": "INFO",
  "log_type": "operation",
  "service": "backend",
  "environment": "production",
  "event": "http_request_completed",
  "request_id": "...",
  "user_id": 1,
  "method": "GET",
  "path": "/strategies/12",
  "route": "/strategies/{subscription_id}",
  "status_code": 200,
  "duration_ms": 31.42,
  "client_ip": "..."
}
```

`path`는 실제 요청 경로, `route`는 집계 가능한 정규화 경로입니다. Grafana의 API별 집계에는 `route`를 사용해 ID마다 시계열이 분리되는 문제를 방지합니다.

## 4. 주요 메트릭

- API: 초당 요청 수, 상태 코드, 5xx 비율, p95 응답시간, 처리 중 요청
- 외부 연동: Upbit 작업별 호출 수·성공/실패·p95 처리시간, WebSocket 상태, 마지막 시세 수신 경과
- DB: 연결 상태, 용량, cache hit, 작업별 query 처리시간
- Worker: 작업별 실행 결과, p95 처리시간, 마지막 성공 이후 경과시간, 현재 실행 수
- 인프라: 호스트 CPU·메모리·디스크, 컨테이너 CPU·메모리
- 로그 pipeline: Alloy/Loki 전송 상태와 dropped entry 증가량

`p95`는 관측 요청의 95%가 그 값 이하에서 끝났다는 뜻입니다. 표본이 없는 시간에는 선을 억지로 0으로 채우지 않으므로 그래프가 비어 있을 수 있습니다.

## 5. Grafana 대시보드

프로비저닝되는 대시보드는 다음 목적별로 구성됩니다.

| 대시보드 | 용도 |
|---|---|
| 메인 요약 | 서비스 상태, 핵심 API·Worker·로그 상태 요약 |
| 서비스 개요 | Backend, Worker, DB, Upbit, 보안·운영 지표 |
| API 트래픽 | route별 요청량, 상태 코드, 오류율, p95 지연 |
| PostgreSQL 모니터링 | 연결, 용량, cache, query 성능 |
| 운영 모니터링 | 호스트·컨테이너 자원, 로그 pipeline, 상세 운영 지표 |

패널 설명은 다음 네 항목을 같은 순서로 작성합니다.

1. 무엇을 측정하는가
2. 정상 범위
3. 값이 없을 때 의미
4. 문제가 생기면 어디를 확인하는가

Worker 마지막 성공은 작업마다 주기가 다르므로 주문 상태 확인, 포지션 불일치 검사, 중단 주문 복구를 각각 숫자 카드로 표시하고 개별 임계값을 사용합니다.

## 6. 저장과 보존

- 1차 로그: Docker `local` driver, Backend/Worker 기준 컨테이너당 10MB × 5개 회전
- 조회 로그: `monitoring_loki_data` volume
- 메트릭: `monitoring_prometheus_data` volume
- Grafana 상태: `monitoring_grafana_data` volume
- 보안 감사 원본: PostgreSQL

Loki와 Prometheus는 단일 EC2의 filesystem volume 기반입니다. 인스턴스·디스크 전체 유실까지 보호하려면 EBS snapshot, 원격 backup 또는 object storage 전환이 필요합니다.

## 7. 로그 유실 판단

Prometheus counter의 현재값은 프로세스 시작 후 누적값이므로 그대로 ‘최근 1시간 유실’로 표시하면 매일 큰 숫자가 남습니다. 최근 1시간 증가는 Grafana Explore의 Prometheus datasource에서 확인합니다.

```promql
sum by (reason, host) (
  increase(loki_write_dropped_entries_total[1h])
)
```

프로젝트에서 사용하는 실제 drop metric 이름과 label은 Prometheus autocomplete/Explore에서 먼저 확인합니다. 재시작 직후 counter reset, label 변화, scrape gap도 함께 봅니다.

## 8. API 지연 분석

1. API별 p95에서 느린 route와 시간을 찾습니다.
2. 같은 시간의 `duration_ms >= 2000` 요청 로그를 request ID로 확인합니다.
3. Upbit API p95와 성공·실패 수를 비교합니다.
4. DB 작업별 query 시간과 PostgreSQL 자원을 확인합니다.
5. 호스트·컨테이너 CPU와 메모리 압박을 확인합니다.

API 성공 응답이 느려도 5xx 패널에는 나타나지 않습니다. 외부 API 대기, DB query, event loop blocking을 분리해 판단해야 합니다.

## 9. PostgreSQL exporter 계정

```sql
CREATE USER monitoring WITH PASSWORD '충분히-긴-무작위-비밀번호';
GRANT CONNECT ON DATABASE fastapi_db TO monitoring;
GRANT pg_monitor TO monitoring;
```

DSN의 특수문자는 URL encoding하고 SSM SecureString에 저장합니다.

```text
/signaltrade/production/monitoring/postgres-exporter-dsn
```

## 10. 운영 접근 제한

Grafana는 `127.0.0.1:3000`에만 bind합니다. 외부 사용자는 `https://<domain>/monitoring/`에서 다음 두 인증을 순서대로 통과합니다.

1. Nginx Basic Auth
2. Grafana 로그인

운영 SSM prefix 아래에는 `grafana-admin-user`, `grafana-admin-password`, `postgres-exporter-dsn`, `proxy-basic-auth`를 SecureString으로 저장합니다. `proxy-basic-auth`는 평문 비밀번호가 아니라 bcrypt htpasswd 한 줄입니다. 3000, 9090, 9100, 9101 등 내부 포트는 Security Group에서 공개하지 않습니다.

## 11. 문제 확인

```bash
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml ps
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml logs alloy loki prometheus grafana
docker compose logs backend strategy-worker frontend
```

- `No data`: 시간 범위, datasource, scrape target, 실제 표본 존재 여부 확인
- 중간 공백: 요청 없음, 컨테이너 재시작, scrape 실패, metric label 변경 확인
- Nginx 502 `/monitoring/api/live/ws`: Grafana 상태와 WebSocket proxy Upgrade 설정 확인
- Telegram 409: 같은 Bot Token으로 polling하는 다른 인스턴스 종료
- CPU/메모리 급증: cAdvisor에서 컨테이너를 찾고 같은 시간의 API·Worker·DB 패널 비교

운영 배포 설정은 [CD_SETUP.md](CD_SETUP.md)를 참고합니다.
