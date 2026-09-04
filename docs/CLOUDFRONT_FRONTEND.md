# S3·CloudFront Frontend 운영

운영 Frontend 정적 파일은 비공개 S3 bucket에 저장하고 CloudFront가 OAC로 읽습니다. 동적 경로는 EKS ALB origin으로 전달합니다.

```text
signaltrade.cloud
  ├─ /*             → CloudFront → private S3
  ├─ /api/*         → CloudFront → eks-origin.signaltrade.cloud:443 → Backend
  ├─ /monitoring*   → CloudFront → eks-origin.signaltrade.cloud:443 → Grafana
  └─ /healthz       → CloudFront → eks-origin.signaltrade.cloud:443 → Backend
```

S3 website hosting과 public access는 사용하지 않습니다. 확장자가 없는 Frontend route는 CloudFront Function이 `/index.html`로 바꿉니다. `/api`, `/monitoring`, `/healthz`는 rewrite하거나 cache하지 않습니다.

## 1. 사전 준비

1. `us-east-1`에 `signaltrade.cloud` ACM certificate를 발급하고 DNS validation을 완료합니다.
2. `eks-origin.signaltrade.cloud`를 EKS ALB Alias로 연결합니다.
3. ALB Security Group은 AWS 관리 prefix list `com.amazonaws.global.cloudfront.origin-facing`만 허용합니다.

CloudFront에서 전달한 `CloudFront-Viewer-Address`를 Nginx가 client IP로 사용하므로, origin을 CloudFront origin-facing prefix list로 제한해야 외부에서 해당 header를 위조할 수 없습니다.

## 2. CloudFormation 배포

[`infrastructure/cloudformation/frontend-cloudfront.yml`](../infrastructure/cloudformation/frontend-cloudfront.yml)을 배포합니다. `HostedZoneId`를 비워 먼저 distribution만 만들고 검증한 다음 DNS를 전환할 수도 있습니다.

```bash
aws cloudformation deploy \
  --region us-east-1 \
  --stack-name signaltrade-frontend \
  --template-file infrastructure/cloudformation/frontend-cloudfront.yml \
  --parameter-overrides \
    DomainName=signaltrade.cloud \
    CertificateArn=<us-east-1-acm-arn> \
    BackendOriginDomainName=eks-origin.signaltrade.cloud \
    HostedZoneId=<public-hosted-zone-id>
```

Stack output의 `FrontendBucketName`과 `DistributionId`를 기록합니다. Bucket에는 Block Public Access, SSE-S3, versioning과 `DeletionPolicy: Retain`이 적용됩니다.

## 3. GitHub production 변수와 IAM

| Variable | 값 |
|---|---|
| `FRONTEND_S3_BUCKET` | Stack output `FrontendBucketName` |
| `CLOUDFRONT_DISTRIBUTION_ID` | Stack output `DistributionId` |

GitHub OIDC deploy role에는 해당 bucket의 `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`와 해당 distribution의 `cloudfront:CreateInvalidation`, `cloudfront:GetInvalidation` 권한이 필요합니다.

## 4. Release 동작

Release workflow는 `VITE_API_BASE_URL=/api`로 build하고 Backend 이미지를 ECR에 게시합니다. Kubernetes 배포는 Argo CD/Helm이 담당하며, Frontend는 `frontend/dist`를 S3와 동기화합니다. 해시 asset은 1년 immutable, 일반 파일은 5분, `index.html`은 no-cache이며 마지막에 `/index.html` invalidation 완료까지 기다립니다.

S3 동기화나 invalidation이 실패하면 workflow도 실패합니다. Backend 배포는 이미 완료됐지만 CloudFront는 기존 정적 버전을 계속 제공할 수 있습니다.

## 5. 전환 확인

```bash
curl -I https://signaltrade.cloud/
curl -I https://signaltrade.cloud/login
curl -I https://signaltrade.cloud/healthz
curl -I https://signaltrade.cloud/api/metrics
```

- `/`와 `/login`은 `200`과 보안 header를 반환해야 합니다.
- `/healthz`는 `200`, `/api/metrics`는 계속 `404`여야 합니다.
- `/monitoring/`은 Basic Auth 없이 `401`이어야 하며 Grafana Live WebSocket도 확인합니다.

문제가 생기면 CloudFront와 EKS ALB 상태를 확인하고 GitOps에서 직전 Backend 이미지로 롤백합니다.
