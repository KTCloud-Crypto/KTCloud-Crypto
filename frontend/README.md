# AutoTrade React + Vite

## 프로젝트 개요

정적 HTML/CSS/JS 데모를 React 컴포넌트와 CSS Module 구조로 변환한 암호화폐 자동매매 대시보드 프론트엔드입니다.

현재는 화면 데모 중심으로 구성되어 있으며, 회원가입 정보 저장이나 백엔드 API 호출은 아직 포함되어 있지 않습니다.

## 프로젝트 구조

```text
frontend/
├── index.html                 # Vite HTML 진입점, root DOM 제공
├── package.json               # npm 스크립트와 프론트엔드 의존성 정의
├── package-lock.json          # npm 의존성 잠금 파일
├── vite.config.js             # Vite 설정
├── eslint.config.js           # ESLint 설정
├── README.md                  # 프론트엔드 프로젝트 설명 문서
└── src/
    ├── main.jsx               # React 앱 렌더링 진입점
    ├── App.jsx                # React Router 라우트 정의
    ├── styles/
    │   └── global.css         # 전역 스타일
    ├── pages/
    │   ├── LoginPage.jsx      # 로그인 화면
    │   ├── LoginPage.module.css
    │   ├── SignupPage.jsx     # 회원가입 화면
    │   ├── SignupPage.module.css
    │   ├── DashboardPage.jsx  # 대시보드 페이지 조립
    │   └── DashboardPage.module.css
    └── components/
        ├── layout/
        │   ├── Sidebar.jsx    # 좌측 메뉴, 모바일 사이드바
        │   ├── Sidebar.module.css
        │   ├── Topbar.jsx     # 상단 바, 메뉴 버튼, 현재 시간 표시
        │   └── Topbar.module.css
        └── dashboard/
            ├── MarketStrip.jsx          # 주요 코인/시장 지표 표시 영역
            ├── MarketStrip.module.css
            ├── MetricCards.jsx          # 계정 요약 수치 카드
            ├── MetricCards.module.css
            ├── PerformancePanel.jsx     # 수익률/성과 패널
            ├── PerformancePanel.module.css
            ├── QuickOrder.jsx           # 빠른 주문, 매수/매도 탭
            ├── QuickOrder.module.css
            ├── StrategyPanel.jsx        # 자동매매 전략 상태/토글
            ├── StrategyPanel.module.css
            ├── RiskPanel.jsx            # 리스크 관리 상태
            ├── RiskPanel.module.css
            ├── OrdersTable.jsx          # 주문/거래 내역 테이블
            ├── OrdersTable.module.css
            ├── BottomPanels.jsx         # 하단 보조 정보 패널
            └── BottomPanels.module.css
```

## 주요 파일 역할

| 파일 | 역할 |
|------|------|
| `index.html` | 브라우저가 처음 로드하는 HTML 파일입니다. `#root` DOM과 `/src/main.jsx` 스크립트를 연결합니다. |
| `src/main.jsx` | React 앱을 생성하고 `BrowserRouter`, `StrictMode`, 전역 CSS를 적용합니다. |
| `src/App.jsx` | `/login`, `/signup`, `/dashboard` 라우팅을 정의합니다. 알 수 없는 경로는 `/login`으로 이동합니다. |
| `src/pages/LoginPage.jsx` | 로그인 화면 UI와 비밀번호 표시/숨김 상태를 처리합니다. |
| `src/pages/SignupPage.jsx` | 회원가입 UI, 입력값 검증, 비밀번호/API Key 표시/숨김 상태를 처리합니다. |
| `src/pages/DashboardPage.jsx` | 사이드바, 탑바, 시장 지표, 주문, 전략, 리스크, 테이블 컴포넌트를 조립하는 대시보드 화면입니다. |
| `src/styles/global.css` | 앱 전체에 공통 적용되는 기본 스타일입니다. |
| `vite.config.js` | Vite React 플러그인 설정 파일입니다. |
| `eslint.config.js` | React Hooks, React Refresh 등을 포함한 ESLint 설정 파일입니다. |

## 라우트 구성

| 경로 | 화면 |
|------|------|
| `/` | `/login`으로 리다이렉트 |
| `/login` | 로그인 페이지 |
| `/signup` | 회원가입 페이지 |
| `/dashboard` | 자동매매 대시보드 |
| `*` | `/login`으로 리다이렉트 |

## 포함 기능

- 로그인 화면
- 회원가입 화면(ID, 비밀번호, 비밀번호 확인, Upbit Access Key, Upbit Secret Key, 닉네임)
- 회원가입 입력값 검증 및 비밀번호/API Key 표시/숨김
- React Router 기반 로그인, 회원가입, 대시보드 이동
- 모바일 사이드바 열기/닫기
- 사이드바 활성 메뉴 표시
- 차트 기간 선택
- 매수/매도 탭
- 주문 비율 선택
- 전략 활성화 토글
- 시스템 현재 시간 표시
- 반응형 레이아웃

## 기술 스택

- React 19
- Vite 7
- React Router DOM 7
- CSS Modules
- lucide-react
- ESLint 9

## 실행

```bash
npm install
npm run dev
```

브라우저:

```text
http://localhost:5173
```

## 배포용 빌드

```bash
npm run build
npm run preview
```

`npm run build` 실행 후 `dist/` 폴더가 생성됩니다.

## 개발 참고사항

- 현재 회원가입 완료 동작은 화면 데모용입니다.
- 입력 정보는 저장하거나 외부로 전송하지 않습니다.
- 실제 회원가입, 로그인, API Key 암호화 저장, 대시보드 데이터 조회는 백엔드 API 연동이 필요합니다.
- 각 화면/컴포넌트 스타일은 같은 이름의 `*.module.css` 파일에 분리되어 있습니다.
