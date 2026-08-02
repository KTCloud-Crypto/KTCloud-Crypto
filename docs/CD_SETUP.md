# SignalTrade 운영 CD 설정

## 배포 흐름

정식 SemVer 태그가 `main`에 포함된 커밋을 가리킬 때만 운영 배포한다.

```text
v0.1.0 태그 push
  -> 기존 CI 전체 통과
  -> GitHub OIDC로 임시 AWS 권한 획득
  -> Backend/Frontend 이미지를 한 번 빌드
  -> ECR에 버전 및 Git SHA 태그로 push
  -> 빌드 결과의 sha256 digest 확정
  -> SSM Run Command로 EC2 배포
  -> 배포 전 PostgreSQL dump 및 S3 업로드
  -> Alembic migration
  -> digest가 고정된 컨테이너 실행
  -> 외부 HTTPS health check
  -> 실패 시 직전 애플리케이션 이미지로 rollback
```

운영 배포 파일은 다음과 같다.

- `.github/workflows/release-production.yml`: 이미지 빌드와 SSM 배포
- `docker-compose.production.yml`: 소스 마운트와 로컬 빌드가 없는 운영 Compose
- `scripts/deploy-production.sh`: 백업, 마이그레이션, 헬스체크, 롤백

## 1. Amazon ECR

동일한 AWS Region에 private repository 두 개를 만든다.

```text
signaltrade/backend
signaltrade/frontend
```

각 저장소에는 다음 설정을 권장한다.

- Tag immutability 활성화
- Image scanning 활성화
- 최근 정식 릴리스 10개 이상 유지
- 태그가 없는 이미지와 오래된 빌드에는 lifecycle policy 적용

운영에서는 태그가 아니라 GitHub Actions가 반환한 image digest를 배포한다.
PostgreSQL base image 업그레이드는 애플리케이션 릴리스와 분리해 별도로 검증한다.

## 2. S3 DB 백업 버킷

배포 전 PostgreSQL custom-format dump를 저장할 private S3 버킷을 만든다.

권장 설정:

- Block Public Access 전체 활성화
- Versioning 활성화
- SSE-KMS 기본 암호화
- lifecycle retention 설정
- 운영 계정 외 삭제 권한 최소화

예시 경로:

```text
s3://signaltrade-production-backups/postgres
```

DB dump에는 사용자와 거래 데이터가 포함되므로 공개 버킷을 사용하면 안 된다.

## 3. EC2 Instance Role

EC2를 Systems Manager managed node로 등록하고 Instance Role에 최소한 다음 권한을 부여한다.

- `AmazonSSMManagedInstanceCore`
- 배포 대상 ECR repository의 image pull 권한
- 백업 경로에 대한 `s3:PutObject`
- ECR 인증을 위한 `ecr:GetAuthorizationToken`
- KMS 암호화 버킷을 사용할 경우 필요한 KMS 권한

EC2에서 다음 명령이 모두 동작해야 한다.

```bash
aws sts get-caller-identity
aws ssm get-parameter --name /does-not-need-to-exist 2>&1 || true
aws ecr get-login-password --region <AWS_REGION> >/dev/null
docker compose version
git --version
curl --version
flock --version
```

Systems Manager 콘솔의 `Fleet Manager > Managed nodes`에서 EC2가 Online인지 확인한다.

## 4. GitHub OIDC Role

AWS IAM에 GitHub OIDC provider를 등록한다.

```text
Provider URL: https://token.actions.githubusercontent.com
Audience: sts.amazonaws.com
```

GitHub Actions용 IAM Role의 trust policy는 저장소와 `production` Environment로 제한한다.

GitHub의 OIDC subject가 immutable 형식을 사용하는 저장소는 이름뿐 아니라 owner/repository ID도 포함한다.
저장소 설정은 `GET /repos/{owner}/{repo}/actions/oidc/customization/sub` 응답의
`sub_claim_prefix`로 확인하고, 실제 prefix에 맞는 조건을 사용한다.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<AWS_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:KTCloud-Crypto@OWNER_ID/KTCloud-Crypto@REPOSITORY_ID:environment:production"
        }
      }
    }
  ]
}
```

GitHub Actions Role에는 다음 권한만 부여한다.

- 대상 ECR repository push
- 대상 EC2에 대한 `ssm:SendCommand`
- 사용한 SSM document에 대한 `ssm:SendCommand`
- 실행 결과 확인을 위한 `ssm:GetCommandInvocation`

AWS Access Key와 EC2 SSH private key는 GitHub에 저장하지 않는다.

## 5. GitHub production Environment

GitHub에서 `Settings > Environments > New environment`로 `production`을 만든다.
필요하면 Required reviewers를 지정해 정식 태그가 생성되어도 승인 후 배포되게 한다.

`production` Environment Variables에 다음 값을 등록한다.

| 이름 | 예시 | 필수 |
|---|---|---:|
| `AWS_REGION` | `us-east-1` | O |
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/signaltrade-github-deploy` | O |
| `ECR_BACKEND_REPOSITORY` | `signaltrade/backend` | O |
| `ECR_FRONTEND_REPOSITORY` | `signaltrade/frontend` | O |
| `EC2_INSTANCE_ID` | `i-0123456789abcdef0` | O |
| `DEPLOY_PATH` | `/home/ubuntu/KTCloud-Crypto` | O |
| `DEPLOY_USER` | `ubuntu` | O |
| `BACKUP_S3_URI` | `s3://signaltrade-production-backups/postgres` | 권장 |
| `HEALTHCHECK_URL` | `https://signaltrade.cloud/healthz` | O |
| `DOCKER_PLATFORM` | `linux/amd64` | O |

위 값은 비밀키가 아니므로 Variables에 저장한다. 장기 AWS credential은 만들지 않는다.

## 6. EC2 최초 준비

최초 한 번은 EC2 저장소에 운영 배포 파일이 존재하도록 `main`을 반영한다.

```bash
cd ~/KTCloud-Crypto
git switch main
git pull --ff-only origin main
chmod +x scripts/deploy-production.sh
```

EC2의 `.env`는 Git에 포함하지 않으며 최소한 다음 운영값을 유지한다.

```dotenv
ENVIRONMENT=production
DOMAIN=signaltrade.cloud
HTTPS_ENABLED=true
ALLOWED_HOSTS=signaltrade.cloud,localhost,127.0.0.1,backend
CORS_ORIGINS=https://signaltrade.cloud
VITE_API_BASE_URL=/api
```

기존 `postgres_data`, `certbot_www`, `letsencrypt` named volume은 운영 Compose에서도
같은 프로젝트 이름으로 사용하므로 삭제하지 않는다.

## 7. 첫 배포

`main`의 배포할 커밋에서 정식 태그를 만든다.

```bash
git switch main
git pull --ff-only origin main
git tag -a v0.1.0 -m "release: v0.1.0"
git push origin v0.1.0
```

GitHub의 `Actions > Release production`에서 다음을 확인한다.

- Verify release 통과
- Backend/Frontend ECR push 성공
- SSM command status가 Success
- HTTPS health check 성공

EC2에서 배포 버전을 확인할 수 있다.

```bash
cd ~/KTCloud-Crypto
cat .deployed-release
cat .release.env
docker compose --env-file .env --env-file .release.env \
  -f docker-compose.production.yml ps -a
```

## 8. 롤백 정책

배포 스크립트는 헬스체크 실패 시 `.release.previous.env`의 이미지 digest로
애플리케이션 컨테이너를 자동 복구한다.

DB migration은 자동 downgrade하지 않는다. 모든 운영 migration은 이전 애플리케이션과
호환되는 expand/contract 방식으로 작성해야 한다. 데이터 복원이 필요한 장애는 배포 전
S3 dump를 새 DB에 복구한 뒤 별도로 전환한다.

## 9. 보안 확인

- EC2 보안 그룹의 공개 inbound는 80/443만 유지한다.
- SSM 전환 후 22를 닫는다.
- 8000, 5432, 5173은 외부에 공개하지 않는다.
- GitHub Environment에 운영 배포 승인자를 설정한다.
- ECR, S3, IAM 권한은 해당 repository/bucket/instance로 제한한다.
- 실제 복구 테스트를 정기적으로 수행한다.
