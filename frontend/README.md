# SignalTrade Frontend

React 19와 Vite로 만든 SignalTrade 웹 UI입니다. 개발 빌드는 Vite를 사용하고, Docker 이미지에서는 Nginx가 정적 파일을 제공하면서 Backend와 Grafana를 리버스 프록시합니다.

## 주요 경로

| 경로 | 화면 |
|---|---|
| `/login` | 로그인 |
| `/signup` | 회원가입 |
| `/password-reset` | Telegram 기반 비밀번호 재설정 |
| `/dashboard` | 모의·실전 통합 요약 |
| `/dashboard/:mode` | 모의 또는 실전 투자 관리 |
| `/analytics` | 사용자 손익·거래 분석 |
| `/settings` | 계정, Upbit API Key, Telegram 설정 |
| `/guide` | 서비스 이용 안내 |
| `/guide/strategies` | 전략 안내 |
| `/guide/upbit-key` | Upbit API Key 발급 안내 |

로그인이 필요한 화면은 저장된 Access Token이 없으면 `/login`으로 이동합니다. 화면에 표시하는 마켓과 전략은 Backend API가 반환한 활성 카탈로그를 사용하므로 개수를 Frontend 문서에 고정하지 않습니다.

## 디렉터리

```text
frontend/
├── src/
│   ├── api/          # Backend API client
│   ├── components/   # 공통 UI와 대시보드 구성요소
│   ├── hooks/        # polling 등 공통 hook
│   ├── pages/        # route별 페이지
│   └── utils/        # 표시 변환과 공통 유틸리티
├── nginx/            # Nginx 템플릿과 proxy 설정
├── public/
├── Dockerfile
└── package.json
```

## API와 프록시

- 브라우저 요청은 기본적으로 같은 origin의 `/api`를 사용합니다.
- Nginx는 `/api`를 Backend로 전달합니다.
- `/monitoring/`은 Basic Auth를 적용한 뒤 Grafana로 전달합니다.
- Grafana Live WebSocket도 같은 하위 경로에서 프록시되므로 운영 변경 시 Upgrade 헤더 설정을 유지해야 합니다.
- `/metrics`와 내부 exporter 포트는 외부에 프록시하지 않습니다.

## 개발 및 검사

```bash
cd frontend
npm ci
npm run dev
npm run lint
npm run build
```

전체 Docker 환경에서는 프로젝트 루트에서 실행합니다.

```bash
docker compose up -d --build frontend
docker compose logs -f frontend
```

로컬 전체 실행과 환경변수는 [../SETUP.md](../SETUP.md), 운영 프록시와 배포는 [../docs/CD_SETUP.md](../docs/CD_SETUP.md)를 참고합니다.
