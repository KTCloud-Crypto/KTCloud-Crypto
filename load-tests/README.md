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

## 고정 RPS 읽기 처리량 테스트

`constant-rps-load.js`는 `accounts.local.json`의 모든 계정을 측정 전에 순차 로그인한 뒤,
측정 구간에는 iteration당 인증 GET 요청을 정확히 한 번 전송합니다. 기본값은 장비 한 대당
10 RPS, 5분이며 `RATE`는 두 장비의 합계가 아니라 각 장비가 발생시킬 RPS입니다.

```bash
k6 run \
  -e BASE_URL=https://signaltrade.cloud \
  -e RATE=10 \
  -e DURATION=5m \
  --summary-export=result-a-rps20.json \
  load-tests/constant-rps-load.js
```

두 개발자가 동시에 실행할 때 전체 목표와 각 장비의 `RATE`는 다음과 같습니다.

| 전체 목표 | 개발자 A | 개발자 B | 시간 |
| ---: | ---: | ---: | ---: |
| 2 RPS | 1 | 1 | 1분 |
| 20 RPS | 10 | 10 | 5분 |
| 40 RPS | 20 | 20 | 5분 |
| 60 RPS | 30 | 30 | 5분 |
| 80 RPS | 40 | 40 | 5분 |
| 100 RPS | 50 | 50 | 5분 |

각 장비의 VU 상한은 해당 장비의 계정 수로 고정됩니다. 서버 응답이 느려져 그 범위에서
목표 RPS를 만들 수 없으면 `dropped_iterations`가 발생하며 테스트가 실패합니다. 단계 사이에는
3~5분, 100 RPS 종료 후에는 10분 동안 서버 회복을 확인합니다.

## VU 기반 읽기·쓰기 혼합 테스트

`mixed-vu-load.js`는 VU마다 서로 다른 계정으로 로그인하고 모의투자 API만 호출합니다.
`WRITE_RATIO`만큼 첫 번째 모의 전략의 투자 비율을 5%와 6% 사이에서 교대로 저장하고,
나머지는 GET 요청을 보냅니다. `enabled=true`, 15분봉을 유지하며 실거래, 입출금, 체결
요청은 보내지 않습니다. 기본 쓰기 비율은 0.1(10%)입니다.

```bash
k6 run \
  -e BASE_URL=https://signaltrade.cloud \
  -e VUS=25 \
  -e DURATION=5m \
  -e WRITE_RATIO=0.1 \
  --summary-export=result-a-mixed-50vu.json \
  load-tests/mixed-vu-load.js
```

두 개발자가 동시에 `VUS=25`로 실행하면 전체 50 VU, 각각 `VUS=50`으로 실행하면 전체
100 VU입니다. 개발자마다 서로 겹치지 않는 50개 계정 파일을 사용해야 합니다.

쓰기 중심 혼합 테스트는 같은 파일에 `WRITE_RATIO=0.4`를 전달합니다. 이 테스트는 읽기
60%와 쓰기 40%로 실행됩니다.

```bash
k6 run \
  -e BASE_URL=https://signaltrade.cloud \
  -e VUS=10 \
  -e DURATION=3m \
  -e WRITE_RATIO=0.4 \
  --summary-export=result-a-write-focused-20vu.json \
  load-tests/mixed-vu-load.js
```

## 두 번째 부하 발생 장비의 고정 RPS 준비

두 번째 개발자도 `constant-rps-load.js`와 자신에게 배정된 50개 계정 파일이 필요합니다.
계정 파일 위치와 이름은 반드시 `load-tests/accounts.local.json`이어야 하며 Git에 추가하지
않습니다.

```bash
cd ~/KTCloud-Crypto
jq 'length' load-tests/accounts.local.json
k6 version
k6 inspect \
  -e RATE=1 \
  -e DURATION=1m \
  load-tests/constant-rps-load.js
```

계정 수가 50이고 inspect 결과에 `constant-arrival-rate`, `rate: 1`, `maxVUs: 50`이 보이면
준비 완료입니다. 두 장비는 같은 시각에 각자 전체 목표 RPS의 절반을 실행합니다.

```bash
k6 run \
  -e BASE_URL=https://signaltrade.cloud \
  -e RATE=10 \
  -e DURATION=5m \
  --summary-export=result-b-rps20.json \
  load-tests/constant-rps-load.js
```

위 명령을 두 장비가 각각 `RATE=10`으로 실행하면 서버 전체에는 20 RPS가 들어갑니다.
