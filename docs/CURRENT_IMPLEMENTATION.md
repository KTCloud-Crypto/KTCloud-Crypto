# 현재 구현 현황

이 문서는 특정 PR이나 로컬 브랜치의 순간 상태가 아니라 현재 코드베이스가 제공하는 기능과 운영 경계를 정리합니다. 실제 병합 여부는 GitHub와 Git 기록을 기준으로 판단합니다.

## 구현된 영역

### 계정과 보안

- JWT 기반 인증과 보호된 Frontend route
- 로그인 실패 누적과 임시 잠금
- Telegram 연동 코드를 이용한 비밀번호 재설정
- Upbit API Key 검증과 암호화 저장
- 계정·인증·민감 설정 변경 보안 감사 로그
- 구조화 로그의 비밀번호, Token, API Key 마스킹

### 투자와 전략

- 모의투자와 실전투자 상태·기록 분리
- Backend/DB 활성 상태 기반 마켓·전략 카탈로그
- 사용자별 마켓·전략·분봉·투자 비율 설정
- WebSocket 체결 기반 분봉과 전략 평가
- 신호, 실행, 주문, 거래 기록
- 전략별 포지션과 투자 할당 관리

### 정합성과 복구

- 미체결 주문 상태 확인
- Upbit 실제 잔고와 내부 포지션 불일치 감지
- 중단된 주문·실행 복구
- Telegram polling과 명령 처리
- Worker 작업별 실행 수, 처리시간, 마지막 성공 시각 수집

### 분석과 UI

- 통합 요약, 모의·실전 대시보드
- 실현손익, 승률, 자산과 거래 분석
- 계정, Upbit API Key, Telegram 설정
- 사용자 가이드와 전략 안내

### 관측성과 운영

- Backend/Worker JSON stdout 로그와 요청 ID
- Nginx access/error 구조화 로그
- Prometheus 애플리케이션·Worker·DB·호스트·컨테이너 메트릭
- Loki 로그 저장과 Grafana 대시보드
- API 지연을 Upbit 외부 호출, DB 쿼리, 느린 요청 로그로 분리
- GitHub Actions CI와 태그 기반 AWS 운영 배포
- 비공개 S3·CloudFront 기반 Frontend 정적 파일 배포와 SPA route rewrite
- Secrets Manager, Parameter Store, SSM SecureString을 이용한 설정 분리
- 배포 전 DB 백업, 마이그레이션, health check, 실패 시 rollback

## 현재 실행 단위

| 구분 | 구성 |
|---|---|
| 애플리케이션 | `frontend` Nginx proxy, `backend`, `strategy-worker`, 외부 RDS, 일회성 `migrate` |
| 모니터링 | `grafana`, `prometheus`, `loki`, `alloy`, `cadvisor`, `node-exporter`, `postgres-exporter` |
| 외부 연동 | Upbit REST/WebSocket, Telegram Bot API |
| 운영 기반 | EC2, RDS, ECR, S3, CloudFront, SSM Run Command, Nginx |

## 운영상 경계

- 마켓과 전략의 개수는 고정 계약이 아니며 활성 카탈로그를 확인해야 합니다.
- Loki와 Prometheus는 현재 단일 호스트 Docker volume 기반이므로 EC2 전체 유실에 대비한 외부 저장·백업 정책이 별도로 필요합니다.
- Grafana는 Nginx Basic Auth와 Grafana 로그인을 모두 거치며 3000 포트를 외부 공개하지 않습니다.
- `/metrics`, exporter 포트, API 문서는 운영 외부망에 공개하지 않습니다.
- 자동매매의 실제 주문 활성화는 사용자 설정과 유효한 Upbit 권한을 모두 필요로 합니다.
- Grafana의 `No data`는 항상 장애를 뜻하지 않습니다. 해당 시간에 요청·작업 표본이 없거나 수집 대상이 재시작됐는지 함께 확인합니다.

## 변경 시 함께 확인할 파일

| 변경 | 확인 대상 |
|---|---|
| API 또는 schema | Backend 테스트, Frontend API client, OpenAPI 개발 문서 |
| DB 모델 | Alembic 단일 head, migration CI, 운영 backup/rollback |
| Worker 작업 | 작업 결과·처리시간·마지막 성공 메트릭과 대시보드 |
| 로그 필드 | Alloy parsing, Loki label cardinality, Grafana LogQL |
| 메트릭 이름 | Prometheus scrape, recording/query, Grafana panel |
| 운영 설정 | GitHub variable, Secrets Manager, Parameter Store, SSM 권한 |

세부 구조는 [ARCHITECTURE_AND_USAGE.md](ARCHITECTURE_AND_USAGE.md), 운영 관측성은 [OBSERVABILITY.md](OBSERVABILITY.md)를 참고합니다.
