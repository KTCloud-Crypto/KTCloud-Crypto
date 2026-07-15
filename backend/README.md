# FastAPI Trading Bot 프로젝트

## 📋 프로젝트 개요

PostgreSQL 기반 FastAPI 거래봇 애플리케이션입니다.

## 🗂️ 프로젝트 구조

```
fastapi/
├── app/
│   ├── api/              # API 라우터
│   │   └── health.py     # 헬스체크 엔드포인트
│   ├── core/             # 핵심 설정
│   │   ├── config.py     # 환경설정 (Pydantic)
│   │   └── database.py   # SQLAlchemy DB 연결
│   ├── models/           # ORM 모델
│   │   ├── user.py
│   │   ├── api_key.py
│   │   ├── trade_history.py
│   │   └── last_signal.py
│   ├── schemas/          # Pydantic 스키마 (요청/응답)
│   ├── services/         # 비즈니스 로직
│   └── main.py           # FastAPI 앱 진입점
├── .env                  # 환경변수 (깃 제외)
├── .env.example          # 환경변수 템플릿
├── .gitignore
├── requirements.txt      # Python 패키지 의존성
└── README.md            # 이 파일
```

## 🔧 기술 스택

- **웹프레임워크**: FastAPI 0.104.1
- **서버**: Uvicorn 0.24.0
- **데이터베이스**: PostgreSQL (포트: 5432)
- **ORM**: SQLAlchemy 2.0.23
- **DB 드라이버**: psycopg2-binary 2.9.9
- **환경설정**: Pydantic Settings 2.1.0
### .env 파일 필수 항목

```bash
# PostgreSQL 연결
DATABASE_URL=postgresql://postgres:password@localhost:5432/fastapi_db

# 환경 설정
ENVIRONMENT=development  # development or production
DEBUG=True

# 서버 설정
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 로컬 개발 환경 설정

```bash
# 1. .env 파일 생성
cp .env.example .env

# 2. .env 파일 수정 (필요한 값 입력)

# 3. 패키지 설치
pip install -r requirements.txt

# 4. FastAPI 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 가상환경 실행

macOS / Linux

```bash
source .venv/bin/activate
```

Windows

```powershell
.venv\Scripts\activate
```

### 4. 라이브러리 설치

```bash
pip install -r requirements.txt
```

---

# ▶️ 서버 실행

```bash
fastapi dev app/main.py
```

또는

```bash
uvicorn app.main:app --reload
```

---