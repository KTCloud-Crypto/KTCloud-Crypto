# k6 부하 테스트

이 디렉터리의 테스트는 서비스 서버가 아닌 외부 장비에서 실행합니다.

## 공개 상태 확인 Smoke 테스트

실제 주문이나 사용자 데이터를 변경하지 않고 `/healthz`와 `/api/health`만 호출합니다.

```bash
k6 run -e BASE_URL=https://signaltrade.cloud load-tests/smoke.js
```

기본 설정은 VU 2개로 30초 동안 실행하며, 실패율 1% 미만과 p95 1초 미만을 요구합니다.

## 인증 읽기 부하 테스트

`.env.loadtest`의 전용 계정으로 시작 시 한 번 로그인하고, 데이터 변경이 없는 핵심 API를
실제 사용 비율에 가깝게 호출합니다. 기본값은 5 VU, 2분입니다.

```bash
set -a
source load-tests/.env.loadtest
set +a
k6 run -e BASE_URL=https://signaltrade.cloud load-tests/authenticated-load.js
```

강도와 실행 시간은 `VUS`, `DURATION` 환경변수로 조정할 수 있습니다.

## 서로 다른 사용자 50명

Upbit 키가 없는 테스트 계정과 모의계좌를 최초 한 번 생성합니다. 자격정보는 Git에서 제외된
`accounts.local.json`에 저장됩니다.

```bash
node load-tests/provision-accounts.mjs
```

각 VU가 서로 다른 계정으로 한 번 로그인한 뒤 읽기 API만 호출합니다.

```bash
k6 run \
  -e BASE_URL=https://signaltrade.cloud \
  -e VUS=50 \
  -e DURATION=5m \
  --summary-export=/tmp/signaltrade-k6-50-users.json \
  load-tests/multi-user-load.js
```
