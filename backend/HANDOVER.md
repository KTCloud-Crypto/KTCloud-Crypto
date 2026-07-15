# 프로젝트 인수인계 문서

## 📋 현재 상태 요약

이 FastAPI 프로젝트는 **도커화를 위한 준비 단계**에서 다음과 같이 완료되어 있습니다.

### ✅ 완료된 것

| 항목 | 상태 | 파일 |
|------|------|------|
| FastAPI 애플리케이션 구조 | ✅ | `app/main.py` |
| PostgreSQL ORM 모델 정의 | ✅ | `app/models/*.py` |
| 데이터베이스 연결 설정 | ✅ | `app/core/database.py` |
| 환경설정 시스템 | ✅ | `app/core/config.py`, `.env` |
| 패키지 의존성 | ✅ | `requirements.txt` |
| 환경변수 템플릿 | ✅ | `.env.example` |
| 로컬 개발 환경 테스트 | ✅ | 완료 |

### ❌ 아직 필요한 것 (도커 담당)

| 항목 | 상태 | 담당 |
|------|------|------|
| Dockerfile | ❌ | 도커 개발자 |
| docker-compose.yml | ❌ | 도커 개발자 |
| .env (프로덕션) | ❌ | 인프라팀 |
| CI/CD 파이프라인 | ❌ | DevOps |

---

## 🗂️ 프로젝트 폴더 구조

```
fastapi/
├── app/
│   ├── __init__.py
│   ├── main.py                 # 📍 FastAPI 앱 진입점
│   ├── api/
│   │   ├── __init__.py
│   │   └── health.py           # GET /health 엔드포인트
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # 📍 Pydantic Settings (환경변수 관리)
│   │   └── database.py         # 📍 SQLAlchemy 연결 설정
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py             # User 테이블 ORM
│   │   ├── api_key.py          # ApiKey 테이블 ORM
│   │   ├── trade_history.py    # TradeHistory 테이블 ORM
│   │   └── last_signal.py      # LastSignal 테이블 ORM
│   ├── schemas/                # (아직 비어있음 - 향후 추가)
│   └── services/               # (아직 비어있음 - 향후 추가)
├── .env                        # 📍 환경변수 (깃 제외)
├── .env.example                # 📍 환경변수 템플릿
├── .gitignore                  # 📍 깃 제외 파일
├── requirements.txt            # 📍 Python 패키지 의존성
├── README.md                   # 📍 프로젝트 가이드
├── DOCKER_SETUP.md             # 📍 도커 담당자용 가이드 (이 문서)
└── HANDOVER.md                 # 📍 인수인계 문서 (이 파일)
```

---

## 🔧 기술 스택

```
Python 3.10+
├── FastAPI 0.104.1          (웹 프레임워크)
├── Uvicorn 0.24.0           (ASGI 서버)
├── SQLAlchemy 2.0.23        (ORM)
├── Pydantic Settings 2.1.0   (환경설정)
└── psycopg2-binary 2.9.9    (PostgreSQL 드라이버)

Database
└── PostgreSQL 15             (데이터베이스)
```

---

## 📊 데이터베이스 스키마

### 테이블 목록 및 구조

#### 1️⃣ user (사용자)
```sql
- id (PK)         : BIGINT AUTO INCREMENT
- username        : VARCHAR(255) UNIQUE
- password        : VARCHAR(255)
- nickname        : VARCHAR(255)
```

#### 2️⃣ api_key (API 키 관리)
```sql
- id (PK)         : BIGINT AUTO INCREMENT
- user_id (FK)    : BIGINT → user.id
- access_key      : VARCHAR(255) UNIQUE
- secret_key      : VARCHAR(255) UNIQUE
- created_at      : DATETIME
```

#### 3️⃣ trade_history (거래 이력)
```sql
- id (PK)         : BIGINT AUTO INCREMENT
- user_id (FK)    : BIGINT → user.id
- stock_name      : VARCHAR(255)
- buy_amount      : DECIMAL(18,2) NULLABLE
- sell_amount     : DECIMAL(18,2) NULLABLE
- traded_at       : DATETIME
```

#### 4️⃣ last_signal (마지막 신호)
```sql
- id (PK)         : BIGINT AUTO INCREMENT
- user_id (FK)    : BIGINT → user.id UNIQUE
- signal_type     : VARCHAR(50)        # BUY, SELL, HOLD
- signal_time     : DATETIME
```

---

## ⚙️ 환경변수 설정

### 필수 환경변수 (.env)

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://postgres:password@localhost:5432/fastapi_db` |
| `SECRET_KEY` | JWT 비밀키 (프로덕션 변경 필수) | `your-secret-key-here` |
| `UPBIT_ACCESS_KEY` | Upbit API Access Key | `your-upbit-access-key` |
| `UPBIT_SECRET_KEY` | Upbit API Secret Key | `your-upbit-secret-key` |
| `ENVIRONMENT` | 환경 구분 | `development` or `production` |
| `DEBUG` | 디버그 모드 | `True` or `False` |
| `SERVER_HOST` | 서버 호스트 | `0.0.0.0` |
| `SERVER_PORT` | 서버 포트 | `8000` |

---

## 🚀 로컬 개발 실행 방법

### 방법 1: 로컬 환경 (Docker 없이)

```bash
# 1. 환경설정
cp .env.example .env
# → .env 파일 수정 (필요한 값 입력)

# 2. 패키지 설치
pip install -r requirements.txt

# 3. PostgreSQL 실행 (별도)
brew services start postgresql@15

# 4. 데이터베이스 생성
createdb fastapi_db

# 5. FastAPI 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. 테스트
curl http://localhost:8000/health
```

### 방법 2: Docker Compose (도커 담당자 작업 후)

```bash
docker-compose up
```

---

## ✅ 테스트 결과

### 로컬 환경에서 이미 검증됨

```
✅ PostgreSQL 15 연결 성공
✅ SQLAlchemy 모델 정의 완료
✅ 4개 테이블 생성 완료
✅ FastAPI 애플리케이션 실행 성공
✅ API 엔드포인트 응답 확인
   - GET / → {"message": "Hello FastAPI"}
   - GET /health → {"status": "ok"}
```

---

## 📝 다음 개발자를 위한 체크리스트

### 도커 담당 개발자 (Docker & docker-compose 작성)

- [ ] [DOCKER_SETUP.md](./DOCKER_SETUP.md) 참고
- [ ] Dockerfile 작성
- [ ] docker-compose.yml 작성
- [ ] 로컬 테스트 완료
- [ ] 문서화 및 배포 가이드 작성

### 백엔드 개발자 (API 엔드포인트 구현)

- [ ] Pydantic schemas 작성 (`app/schemas/`)
- [ ] CRUD 엔드포인트 구현 (`app/api/`)
- [ ] 비즈니스 로직 구현 (`app/services/`)
- [ ] 테스트 코드 작성
- [ ] API 문서 (Swagger) 확인

### 인프라/DevOps (배포 및 CI/CD)

- [ ] 프로덕션 환경 설정 (.env.production)
- [ ] CI/CD 파이프라인 구축 (GitHub Actions, GitLab CI 등)
- [ ] 컨테이너 레지스트리 설정 (Docker Hub, ECR 등)
- [ ] Kubernetes 배포 (필요 시)
- [ ] 모니터링 및 로깅 설정

---

## 📞 주요 연락사항

| 항목 | 담당 |
|------|------|
| PostgreSQL DB 설계 | 백엔드 개발자 |
| Docker 이미지 빌드 | 도커/DevOps |
| 프로덕션 배포 | 인프라팀 |
| API 문서 | 백엔드 개발자 |

---

## 🎯 최종 목표

이 프로젝트가 완성되면:

1. **Docker로 패키징됨** → 어느 환경에서나 동일하게 실행
2. **PostgreSQL 통합** → 프로덕션급 데이터베이스 사용
3. **환경변수 관리** → 보안성 높은 설정 관리
4. **REST API 완성** → 모든 데이터 CRUD 가능
5. **CI/CD 자동화** → 배포 자동화

---

**작성일**: 2026-07-14  
**상태**: Docker 준비 완료 ✅
