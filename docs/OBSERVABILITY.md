# 로그 및 모니터링 운영

애플리케이션은 한 줄 JSON을 표준 출력으로 기록합니다. Docker `local` 로깅 드라이버가
컨테이너별 최대 10MB 파일 5개를 1차 보관하고, Grafana Alloy가 Docker 로그를 Loki로
전송합니다. Loki 데이터는 `monitoring_loki_data` Docker 볼륨에 저장되며 기본 보존 기간은
30일, `debug` 로그는 7일입니다. 보안 감사 이벤트는 PostgreSQL의
`security_audit_log`에도 별도로 보관합니다.

## 실행 순서

모니터링 네트워크를 먼저 생성하기 위해 monitoring Compose를 먼저 시작합니다.

```bash
cp monitoring/.env.example monitoring/.env
# monitoring/.env의 관리자 비밀번호를 반드시 변경
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml up -d
docker compose up -d
```

운영 배포에서도 `signaltrade-observability` 네트워크가 먼저 존재해야 합니다. Grafana는
기본적으로 `127.0.0.1:3000`에만 노출됩니다. 외부 접속은 TLS와 인증이 설정된 리버스
프록시 또는 SSH 터널을 사용합니다.

운영에서는 기존 Nginx가 Grafana를 다음 하위 경로로 프록시합니다.

```text
https://signaltrade.cloud/monitoring/
```

3000 포트는 계속 loopback에만 바인딩하며 Security Group에 공개하지 않습니다. 운영 배포
스크립트는 `/signaltrade/production/monitoring` 아래의 SSM SecureString을 읽어 비밀값을
디스크에 기록하지 않고 Compose 실행 환경으로만 전달한 뒤, 모니터링 스택을
애플리케이션보다 먼저 실행합니다.

- `grafana-admin-user`
- `grafana-admin-password`
- `postgres-exporter-dsn`
- `proxy-basic-auth`

`proxy-basic-auth` 값은 평문 비밀번호가 아니라 `htpasswd` 한 줄 전체입니다. 외부 요청은
Nginx Basic Auth를 먼저 통과한 다음 Grafana 로그인을 한 번 더 거칩니다.
배포 서버에는 소유자 전용 디렉터리 아래 bcrypt 해시 파일만 저장되며 평문 비밀번호는
저장되지 않습니다.

## 설정

- `LOG_LEVEL`: 기본 `INFO`
- `LOG_FORMAT`: 기본 `json`
- `LOG_DEBUG_ENABLED`: 운영 환경에서 DEBUG 허용 여부, 기본 `false`
- `METRICS_ENABLED`: Prometheus endpoint 활성화 여부, 기본 `true`
- `WORKER_METRICS_PORT`: worker metric port, 기본 `9101`
- `TRUSTED_PROXY_CIDRS`: 전달된 클라이언트 IP 헤더를 신뢰할 프록시 CIDR

API 메트릭은 `/metrics`, worker 메트릭은 내부 포트 `9101`에서 수집됩니다. `/metrics`는
외부 프록시에서 공개하지 않아야 합니다.

## 저장 위치와 백업

- 단기 원본: Docker 데이터 루트의 `local` logging driver 파일
- 조회용 로그: `monitoring_loki_data` 볼륨
- 메트릭: `monitoring_prometheus_data` 볼륨
- Grafana 설정: `monitoring_grafana_data` 볼륨
- 보안 감사 원본: PostgreSQL `security_audit_log`

Docker 내부 파일을 직접 복사하지 말고 Loki 볼륨과 PostgreSQL 백업을 정기 스냅샷 또는
원격 객체 스토리지로 백업합니다. 현재 Loki는 단일 서버용 filesystem 저장소이므로 서버가
유실되면 Loki 로그도 유실됩니다. 장기 운영 단계에서는 Loki object storage를 S3로
전환하는 것을 권장합니다.

## PostgreSQL Exporter 계정

애플리케이션 DB 계정을 exporter에서 재사용하지 않습니다. PostgreSQL 관리자 세션에서
전용 계정을 만든 뒤 monitoring `.env`에 DSN을 설정합니다.

```sql
CREATE USER monitoring WITH PASSWORD '충분히-긴-무작위-비밀번호';
GRANT CONNECT ON DATABASE fastapi_db TO monitoring;
GRANT pg_monitor TO monitoring;
```

```env
POSTGRES_EXPORTER_DSN=postgresql://monitoring:URL인코딩된비밀번호@db:5432/fastapi_db?sslmode=disable
```

Grafana에는 `SignalTrade API Traffic`, `SignalTrade PostgreSQL`,
`SignalTrade Service Overview` 대시보드가 자동 등록됩니다. API 대시보드는 정규화된
route별 요청량, 5xx 비율, p95 지연, 상태 코드와 진행 중 요청을 표시합니다.

## 실제 클라이언트 IP

Nginx는 외부에서 들어온 `X-Forwarded-For` 값을 폐기하고 직접 연결한 클라이언트 주소를
backend로 전달합니다. backend는 연결 상대가 `TRUSTED_PROXY_CIDRS`에 포함될 때만 이
헤더를 신뢰합니다. 로드밸런서나 CDN을 추가할 경우 해당 프록시 CIDR만 명시적으로 추가하고
인터넷 전체 대역을 신뢰하지 않습니다.
