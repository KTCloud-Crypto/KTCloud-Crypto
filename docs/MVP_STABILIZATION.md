# MVP 안정화 및 확장 기록

이 문서는 SignalTrade MVP에서 운영 가능한 구조로 확장하며 적용한 핵심 원칙을 기록합니다. 과거의 테스트 개수나 고정 마켓 수 같은 순간 값은 기록하지 않고 현재도 유효한 설계 결정을 남깁니다.

## 1. API와 Worker 분리

초기에는 웹 요청과 자동매매 작업의 생명주기가 섞일 수 있었지만, 현재는 Backend와 `strategy-worker`를 별도 프로세스로 운영합니다. 같은 이미지를 사용하되 API 재시작이 시세 수신과 주문 후속 처리를 직접 담당하지 않도록 역할을 분리했습니다.

## 2. DB 마이그레이션 선행

모든 상시 프로세스가 임의로 테이블을 만들지 않습니다. 일회성 `migrate` 컨테이너가 `alembic upgrade head`를 완료한 뒤 Backend와 Worker가 시작합니다. 병렬 개발에서 revision이 갈라지면 merge revision으로 단일 head를 유지합니다.

## 3. 마켓·전략 카탈로그 일반화

마켓과 전략을 사용자 테이블의 고정 컬럼이나 문서상의 고정 개수로 다루지 않습니다. 카탈로그와 활성 상태, 사용자별 조합 설정을 분리해 항목 추가·비활성화가 기존 주문·포지션 기록의 참조를 깨지 않도록 구성했습니다.

## 4. 모의·실전 데이터 경계

모의투자와 실전투자는 같은 사용자 경험을 공유하지만 계좌, 포지션, 주문, 실행 기록은 모드로 구분합니다. 실전 주문은 사용자 활성화, API Key 검증, 가용 잔고, 중복 주문과 포지션 상태를 확인한 뒤 실행합니다.

## 5. 포지션과 주문 정합성

내부 기록만 신뢰하지 않고 Upbit 주문·잔고와 주기적으로 비교합니다.

- 주문 상태 확인: 미체결·진행 중 주문의 최신 상태 반영
- 포지션 불일치 검사: 실제 잔고와 내부 전략 포지션 비교
- 중단 주문 복구: 프로세스 중단 사이 남은 실행 상태 복원

각 작업의 실행 횟수, 결과, p95 처리시간, 마지막 성공 시각을 메트릭으로 남깁니다. 마지막 성공 경과시간은 작업별 주기에 맞는 임계값으로 판단합니다.

## 6. 외부 API 장애 분리

API 전체 지연만으로 원인을 추측하지 않도록 다음을 별도로 관측합니다.

- Upbit 작업별 호출 수와 성공·실패 결과
- Upbit API p95 처리시간
- DB 작업별 쿼리 처리시간
- 2초 이상 HTTP 느린 요청 로그

외부 통신은 timeout과 제한된 retry를 사용하고, 무한 재시도나 실패 로그 폭증을 피합니다.

## 7. Telegram 안정화

Telegram long polling은 같은 Bot Token당 한 인스턴스만 실행합니다. 둘 이상의 Worker가 `getUpdates`를 호출하면 Telegram이 409 Conflict를 반환합니다. 연동 코드는 만료, 일회성 사용, 사용자 연결 상태를 검사하며 평문 인증정보는 로그에 남기지 않습니다.

## 8. 로그와 메트릭 운영

- 로그는 한 줄 JSON stdout으로 통일했습니다.
- 요청·오류·보안·Worker 작업 로그를 구분합니다.
- Docker 로그 회전으로 로컬 디스크 무제한 증가를 방지합니다.
- Alloy → Loki, Prometheus → Grafana 흐름으로 중앙 조회합니다.
- 반복되는 정상 INFO 로그는 메트릭으로 대체하고 상태 변화·실패·복구 중심으로 기록합니다.
- 로그 유실 수치는 누적 counter 자체가 아니라 선택 기간의 `increase()`로 판단합니다.

## 9. 배포 안정화

운영 배포는 `main`에 포함된 SemVer 태그로만 시작합니다. CI를 통과한 이미지를 ECR digest로 고정하고 EC2에서 migration, health check를 수행합니다. 실패 시 이전 release 환경과 이미지 digest로 되돌릴 수 있게 유지합니다.

설정은 역할별로 분리합니다.

- Secrets Manager: 애플리케이션 비밀값
- Parameter Store: 비민감 운영 설정
- SSM SecureString: Grafana, exporter, Monitoring Basic Auth
- GitHub Variables: secret이 아닌 배포 식별자와 경로

## 10. 앞으로의 확장 원칙

- 카탈로그 확장 전 전략·마켓별 데이터 충분성과 부하를 검증합니다.
- 다중 Worker로 확장할 때 작업 소유권과 Telegram polling leader를 명시합니다.
- 단일 EC2 볼륨에 저장된 Loki·Prometheus 데이터는 장기적으로 외부 object storage와 원격 보관을 검토합니다.
- 알림은 실제 운영 기준과 담당 대응 절차가 정해진 뒤 추가합니다.

현재 기능 목록은 [CURRENT_IMPLEMENTATION.md](CURRENT_IMPLEMENTATION.md), 시스템 흐름은 [ARCHITECTURE_AND_USAGE.md](ARCHITECTURE_AND_USAGE.md)를 참고합니다.
