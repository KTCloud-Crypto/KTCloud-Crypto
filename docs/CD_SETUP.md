# CI/CD 및 AWS 운영 배포

운영 배포는 `main`에 포함된 SemVer 태그(`vMAJOR.MINOR.PATCH`)를 기준으로 수행합니다. GitHub Actions는 AWS OIDC 임시 권한을 사용하며 장기 Access Key나 EC2 SSH Key를 저장하지 않습니다.

## 1. Workflow 구성

| 파일 | 역할 |
|---|---|
| `ci-gate.yml` | 변경 경로 감지 후 Backend/Frontend CI를 호출하고 최종 gate 제공 |
| `backend-ci.yml` | PostgreSQL, migration, Alembic 검증, pytest, 이미지 build |
| `frontend-ci.yml` | `npm ci`, lint, production build, 이미지 build |
| `validate-release-source.yml` | `main` PR의 source 정책 검증 |
| `release-production.yml` | 태그 검증, ECR push, SSM Run Command, S3·CloudFront 배포 |

권장 흐름은 feature branch → `develop` PR → CI 통과 → `main` 반영 → release tag입니다.

## 2. 운영 배포 흐름

```text
main commit에 SemVer tag push
→ tag가 main에 포함됐는지 검증
→ GitHub OIDC로 AWS 임시 권한 획득
→ Backend/Nginx proxy image build 또는 기존 image 확인
→ ECR push와 sha256 digest 확정
→ SSM Run Command로 EC2 deploy script 실행
→ EC2 Role로 config와 secret 조회
→ 외부 RDS PostgreSQL 연결 확인과 backup
→ Alembic migration
→ digest 고정 image 실행
→ 외부 HTTPS health check
→ Frontend build 결과를 private S3에 동기화
→ CloudFront index cache 무효화
→ 실패 시 이전 release로 rollback
```

`docker-compose.production.yml`에는 source mount나 로컬 build가 없으며 GitHub Actions가 확정한 image digest를 사용합니다.

## 3. AWS 자원

### ECR

- Backend repository: 예 `signaltrade/backend`
- Frontend repository: 예 `signaltrade/frontend`
- tag immutability와 image scanning 권장
- 오래된 untagged image는 lifecycle policy로 정리

### S3 backup

배포 전 PostgreSQL custom-format dump 저장에 사용합니다. Block Public Access, encryption, versioning, lifecycle을 적용합니다. 사용자와 거래 데이터가 있으므로 public bucket을 사용하지 않습니다.

EC2 로컬 dump는 최근 72시간만 보관합니다. S3에 업로드된 dump의 장기 보관 기간은 bucket lifecycle policy로 관리합니다.

Frontend asset bucket은 DB backup bucket과 분리하며 public access를 차단하고 CloudFront OAC만 읽도록 허용합니다. 자세한 구성과 DNS 전환 절차는 [CLOUDFRONT_FRONTEND.md](CLOUDFRONT_FRONTEND.md)를 참고합니다.

### EC2와 Instance Role

EC2는 SSM Managed Node로 등록하고 다음 최소 권한을 가집니다.

- `AmazonSSMManagedInstanceCore`
- 대상 ECR pull과 `ecr:GetAuthorizationToken`
- 지정 backup prefix의 `s3:PutObject`
- 지정 Secrets Manager secret의 `GetSecretValue`
- 지정 Parameter Store와 monitoring prefix의 `ssm:GetParameter`
- 고객 관리 KMS key 사용 시 필요한 `kms:Decrypt`

권한 Resource를 account 전체가 아니라 실제 secret, parameter, repository, bucket prefix로 제한합니다.

### GitHub OIDC Role

OIDC provider는 `https://token.actions.githubusercontent.com`, audience는 `sts.amazonaws.com`입니다. trust policy는 repository와 GitHub `production` environment subject로 제한합니다.

이 Role에는 대상 ECR push, 대상 EC2의 `ssm:SendCommand`·`ssm:GetCommandInvocation`, Frontend bucket 동기화와 CloudFront invalidation 권한만 부여합니다. 애플리케이션 secret 조회는 EC2 Instance Role이 담당합니다.

## 4. GitHub production Environment

`Settings > Environments`에 `production`을 만들고 필요하면 required reviewer를 설정합니다.

| Variable | 설명 | 필수 |
|---|---|---:|
| `AWS_REGION` | ECR·SSM Region | O |
| `AWS_DEPLOY_ROLE_ARN` | GitHub OIDC Role ARN | O |
| `ECR_BACKEND_REPOSITORY` | Backend ECR 이름 | O |
| `ECR_FRONTEND_REPOSITORY` | Frontend ECR 이름 | O |
| `FRONTEND_S3_BUCKET` | 비공개 Frontend asset bucket 이름 | O |
| `CLOUDFRONT_DISTRIBUTION_ID` | 운영 CloudFront distribution ID | O |
| `EC2_INSTANCE_ID` | 배포 대상 managed node | O |
| `DEPLOY_PATH` | EC2 repository 경로 | O |
| `DEPLOY_USER` | 배포 OS 사용자 | O |
| `HEALTHCHECK_URL` | 외부 HTTPS health URL | O |
| `SECRETS_MANAGER_SECRET_ID` | 애플리케이션 secret ID/ARN | O |
| `PARAMETER_STORE_CONFIG_ID` | 운영 config parameter ID/ARN | O |
| `BACKUP_S3_URI` | DB backup prefix | 권장 |
| `MONITORING_SSM_PREFIX` | Monitoring SecureString prefix | O |
| `MONITORING_PUBLIC_URL` | Grafana 외부 하위 경로 URL | O |
| `DOCKER_PLATFORM` | 예 `linux/amd64` | O |

이 값들은 식별자와 경로이므로 GitHub Variables에 둡니다. 실제 비밀번호와 Token은 넣지 않습니다.

## 5. 설정과 secret 분리

### AWS Secrets Manager

DB 접속 정보, JWT 서명키, 암호화 키, Upbit/Telegram 공통 비밀값처럼 노출되면 안 되는 애플리케이션 값을 저장합니다. 운영 DB 접속에는 `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_SSLMODE=require`를 사용하며 deploy script가 SSL이 포함된 `DATABASE_URL`을 임시로 생성합니다.

### Parameter Store config

환경 이름, host, CORS, logging/metrics flag, 작업 주기처럼 비밀이 아닌 운영 설정을 JSON parameter로 관리합니다.

### Monitoring SecureString

기본 prefix가 `/signaltrade/production/monitoring`이면 다음 이름을 만듭니다.

```text
grafana-admin-user
grafana-admin-password
postgres-exporter-dsn
proxy-basic-auth
```

`proxy-basic-auth`는 `username:bcrypt-hash` 형식의 htpasswd 한 줄이며 평문 비밀번호가 아닙니다. Parameter ARN 두 개를 붙여 넣지 말고 각 parameter를 별도로 생성합니다.

## 6. EC2 최초 준비

EC2에는 Docker, Compose v2, Git, AWS CLI, curl, flock이 필요합니다. repository는 `main`을 checkout하고 deploy script에 실행 권한을 줍니다.

```bash
cd /home/ubuntu/KTCloud-Crypto
git switch main
git pull --ff-only origin main
chmod +x scripts/deploy-production.sh
aws sts get-caller-identity
docker compose version
```

`.env`를 EC2에 영구 보관하지 않습니다. deploy script가 Secrets Manager와 Parameter Store 값을 임시 env 파일로 만들고 종료 시 제거합니다. Docker container label에 임시 파일 경로가 보일 수 있지만 값 자체가 저장되는 것은 아닙니다.

PostgreSQL exporter는 별도 계정을 사용합니다.

```sql
CREATE USER monitoring WITH PASSWORD '새로운-긴-무작위-비밀번호';
GRANT CONNECT ON DATABASE fastapi_db TO monitoring;
GRANT pg_monitor TO monitoring;
```

## 7. Monitoring 외부 접근

- Grafana container는 `127.0.0.1:3000`에만 bind합니다.
- 외부 URL은 Nginx의 `/monitoring/` reverse proxy만 사용합니다.
- Nginx Basic Auth 후 Grafana 계정으로 다시 로그인합니다.
- Security Group에 Grafana, Prometheus, Loki, exporter 포트를 공개하지 않습니다.
- Grafana Live를 위해 `/monitoring/api/live/`의 WebSocket Upgrade proxy 설정을 유지합니다.

## 8. Release 실행

CI가 모두 성공하고 해당 commit이 `main`에 포함됐는지 확인한 뒤 이전 태그와 변경 성격을 비교해 version을 정합니다.

- PATCH: bug fix, 문서, 호환되는 운영 개선
- MINOR: 하위 호환 기능 추가
- MAJOR: 호환되지 않는 API·schema·운영 계약 변경

```bash
git switch main
git pull --ff-only origin main
git tag -a vX.Y.Z -m "SignalTrade vX.Y.Z"
git push origin vX.Y.Z
```

같은 태그를 다른 commit으로 다시 사용하지 않습니다. workflow run에서 image digest, SSM command ID, migration, health check 결과를 확인합니다.

## 9. 실패와 rollback

deploy script는 lock으로 동시 배포를 막고, 이전 release 환경을 보존한 뒤 migration과 health check를 수행합니다. 실패하면 이전 image digest로 애플리케이션을 복원합니다.

DB schema가 되돌릴 수 없는 방식으로 변경되면 image rollback만으로 충분하지 않습니다. migration은 expand/contract 방식으로 작성하고 backup 복원 절차를 release 전에 검증합니다.

진단 순서:

```bash
aws ssm list-command-invocations --details --region <region>
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs migrate backend strategy-worker frontend
curl -fsS https://<domain>/healthz
```

### 자주 발생하는 원인

- SSM parameter 누락 또는 EC2 Role의 decrypt 권한 부족
- Secrets Manager/Parameter Store JSON key 불일치
- Alembic multiple heads
- ECR login 또는 digest pull 실패
- 외부 health URL·TLS·Nginx 설정 오류
- `/monitoring/api/live/ws` Upgrade proxy 누락

관측성 세부값은 [OBSERVABILITY.md](OBSERVABILITY.md), 현재 구현 범위는 [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md)를 참고합니다.
