# SignalTrade Frontend

React와 Vite로 만든 SignalTrade 사용자 대시보드입니다.

## 제공 기능

- 회원가입·로그인과 JWT 인증
- Upbit 실계좌 잔고 및 거래내역 조회
- 6개 지원 종목 선택
- 사용자·모드·종목·전략 조합별 분봉·투자 비율·손절·익절 설정
- 최신 SMA 계산값과 교차 신호 조회
- 모의/실전 실행 모드 설정
- Telegram 계정 연동

전략 관리 화면에서 종목을 먼저 선택하면 해당 종목의 5개 전략 설정을 조회합니다. 투자 비율 배지는 현재 종목만이 아니라 같은 모드의 모든 종목에 활성화된 전략 합계를 표시합니다.

## 주요 구조

```text
src/
├── api/         # 인증 토큰을 포함하는 공통 API 요청
├── components/  # 대시보드와 레이아웃 컴포넌트
├── hooks/       # 공통 polling 로직
├── pages/       # 로그인, 회원가입, 대시보드 화면
├── styles/      # 전역 스타일
└── utils/       # 날짜와 숫자 표시 유틸
```

## 실행 및 검사

프로젝트 전체를 실행할 때는 루트에서 Docker Compose를 사용합니다.

```bash
docker compose up --build -d
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
```

기본 접속 주소는 `http://localhost:5173`입니다. API 주소는
`VITE_API_BASE_URL` 환경변수로 지정합니다.
