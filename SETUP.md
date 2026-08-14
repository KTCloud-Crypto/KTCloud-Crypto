# SignalTrade 설치 및 실행

이 문서는 현재 Docker Compose 구성을 기준으로 로컬 개발 환경을 시작하는 방법을 설명합니다. 운영 배포는 [docs/CD_SETUP.md](docs/CD_SETUP.md)를 따릅니다.

## 1. 요구 사항

- Docker Engine 또는 Docker Desktop
- Docker Compose v2
- Git
- 선택: Upbit API Key, Telegram Bot Token

## 2. 저장소와 환경 파일

```bash
git clone <repository-url>
cd KTCloud-Crypto
cp .env.example .env
cp monitoring/.env.example monitoring/.env
```

`.env.example`과 `monitoring/.env.example`을 기준으로 값을 채웁니다. 실제 비밀값을 Git에 커밋하지 않습니다.

애플리케이션의 핵심 값은 다음과 같습니다.

| 항목 | 용도 |
|---|---|
| PostgreSQL 사용자·비밀번호·DB | 애플리케이션 데이터 저장 |
| `DATABASE_URL` | Backend와 Worker의 DB 연결 |
| `SECRET_KEY` | 인증 Token 서명 |
| `MASTER_ENCRYPTION_KEY` | Upbit API Key 암호화 |
| Telegram 설정 | 계정 연동과 알림; 사용하지 않으면 비활성화 가능 |

Fernet 호환 키는 다음과 같이 생성할 수 있습니다.

```bash
python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

모니터링 환경에는 Grafana 관리자 계정과 PostgreSQL exporter DSN을 설정합니다. exporter는 애플리케이션 DB 계정이 아닌 `pg_monitor` 권한의 전용 계정을 권장합니다.

## 3. 로컬 Monitoring Basic Auth

Nginx의 `/monitoring/` 경로 테스트를 위해 bcrypt 형식의 htpasswd 파일을 준비합니다.

```bash
docker run --rm httpd:2.4-alpine \
  htpasswd -nbB local-monitor '로컬에서만-사용할-비밀번호' \
  > monitoring/.htpasswd
```

이 파일과 평문 비밀번호를 커밋하지 않습니다.

## 4. 실행 순서

애플리케이션 Compose가 `signaltrade-observability` 외부 네트워크를 사용하므로 모니터링 스택을 먼저 시작합니다.

```bash
docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  up -d

docker compose up -d --build
```

`migrate` 컨테이너가 `alembic upgrade head`를 완료한 뒤 Backend와 Worker가 시작됩니다.

```bash
docker compose ps
docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  ps
```

## 5. 접속 주소

| 대상 | 주소 |
|---|---|
| Web UI | <http://localhost> |
| Backend health | <http://localhost:8000/health> |
| Swagger UI | <http://localhost:8000/docs> |
| Grafana 직접 접속 | <http://localhost:3000> |
| Nginx 경유 Grafana | <http://localhost/monitoring/> |

운영에서는 API 문서가 비활성화되며 Grafana 3000 포트도 외부에 공개하지 않습니다.

## 6. 확인과 테스트

```bash
curl http://localhost:8000/health
docker compose logs migrate
docker compose exec backend python -m pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose build
```

마이그레이션 head가 하나인지 확인합니다.

```bash
docker compose exec backend alembic heads
docker compose exec backend alembic current
```

`Multiple head revisions`가 나오면 임의로 `heads`를 운영 DB에 적용하지 말고 merge revision을 작성해 단일 head로 합칩니다.

## 7. 로그와 상태 확인

```bash
docker compose logs -f backend strategy-worker frontend db
docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  logs -f prometheus loki alloy grafana
```

Backend와 Worker 로그는 stdout JSON이며 Docker `local` logging driver가 회전 보관한 뒤 Alloy가 Loki로 전달합니다.

## 8. 중지와 재시작

```bash
docker compose down
docker compose \
  --env-file monitoring/.env \
  -f monitoring/docker-compose.yml \
  down
```

일반 `down`은 named volume을 유지합니다. `down -v`는 PostgreSQL, Loki, Prometheus, Grafana 데이터를 삭제하므로 데이터 삭제가 명확한 목적일 때만 사용합니다.

## 9. 자주 발생하는 문제

### 외부 네트워크가 없다는 오류

모니터링 Compose를 먼저 실행합니다. 이 과정에서 `signaltrade-observability` 네트워크가 생성됩니다.

### Backend가 시작되지 않음

```bash
docker compose ps -a
docker compose logs migrate backend db
```

DB health, 마이그레이션 실패, `.env`의 DB 접속값 일치를 확인합니다.

### Grafana에 데이터가 없음

```bash
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml ps
docker compose --env-file monitoring/.env -f monitoring/docker-compose.yml logs alloy prometheus
```

서비스가 실제 요청이나 Worker 작업을 처리했는지, Grafana 시간 범위와 KST 표시가 맞는지도 확인합니다.

### Telegram polling 409

같은 Bot Token으로 `getUpdates`를 호출하는 polling 프로세스가 둘 이상이라는 뜻입니다. 운영 Worker, 로컬 Worker, 별도 스크립트 중 하나만 실행합니다.

## 관련 문서

- [프로젝트 구조와 데이터 흐름](docs/ARCHITECTURE_AND_USAGE.md)
- [로그 및 모니터링 운영](docs/OBSERVABILITY.md)
- [CI/CD 및 AWS 운영 배포](docs/CD_SETUP.md)
