# Docker 담당 개발자용 - 필요한 작업

## 📋 현재 상태

현재 프로젝트는 다음이 완료되어 있습니다:
- ✅ FastAPI 애플리케이션 구조
- ✅ PostgreSQL 데이터베이스 모델 정의
- ✅ 환경설정 시스템 (.env 관리)
- ✅ requirements.txt (모든 의존성)
- ✅ 로컬 개발 환경 테스트 완료

## 🐳 Docker 작업 체크리스트

### 필수 파일 생성

- [ ] **Dockerfile 생성**
  - [ ] Python 3.10 베이스 이미지 사용
  - [ ] 워킹 디렉토리: `/app`
  - [ ] requirements.txt 복사 및 설치
  - [ ] 포트 8000 노출
  - [ ] 실행 명령어: `uvicorn app.main:app --host 0.0.0.0 --port 8000`

- [ ] **docker-compose.yml 생성**
  - [ ] PostgreSQL 15 서비스 정의
    - [ ] POSTGRES_USER: postgres
    - [ ] POSTGRES_PASSWORD: password
    - [ ] POSTGRES_DB: fastapi_db
    - [ ] 포트: 5432 매핑
    - [ ] 볼륨: postgres_data 설정
  - [ ] FastAPI 애플리케이션 서비스
    - [ ] Dockerfile을 이용한 빌드
    - [ ] 포트: 8000 매핑
    - [ ] DATABASE_URL 환경변수 설정
    - [ ] db 서비스에 의존성 설정 (depends_on)
    - [ ] 볼륨 마운트 (개발용)

### 환경설정

- [ ] **.env 파일 설정**
  - [ ] DATABASE_URL=postgresql://postgres:password@db:5432/fastapi_db
  - [ ] SECRET_KEY 설정 (프로덕션에서 변경)
  - [ ] UPBIT_ACCESS_KEY 설정
  - [ ] UPBIT_SECRET_KEY 설정
  - [ ] ENVIRONMENT=development (개발) 또는 production (프로덕션)
  - [ ] DEBUG=True (개발) 또는 False (프로덕션)

### 테스트

- [ ] **로컬 Docker 테스트**
  ```bash
  docker-compose up
  ```

- [ ] **서비스 정상 작동 확인**
  - [ ] FastAPI 헬스체크: `GET http://localhost:8000/health`
  - [ ] 응답: `{"status": "ok"}`

- [ ] **데이터베이스 연결 확인**
  ```bash
  docker-compose exec db psql -U postgres -d fastapi_db -c "SELECT * FROM \"user\";"
  ```

- [ ] **테이블 생성 확인**
  - [ ] user
  - [ ] api_key
  - [ ] trade_history
  - [ ] last_signal

### 문제 해결

**Docker 빌드 실패 시:**
- requirements.txt 경로 확인
- Python 버전 호환성 확인
- 패키지 설치 순서 확인

**데이터베이스 연결 실패 시:**
- docker-compose.yml의 DATABASE_URL 확인
- 서비스 이름과 호스트명 일치 확인 (localhost → db)
- depends_on 설정 확인

**포트 충돌 시:**
- `lsof -i :8000` (FastAPI)
- `lsof -i :5432` (PostgreSQL)
- docker-compose.yml에서 포트 변경

---

## 📝 Dockerfile 예제

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 시스템 패키지 업데이트
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 노출
EXPOSE 8000

# 헬스체크 (선택)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 서버 시작
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📝 docker-compose.yml 예제

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: fastapi_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: fastapi_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    container_name: fastapi_app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:password@db:5432/fastapi_db
      SECRET_KEY: your-secret-key
      ENVIRONMENT: development
      DEBUG: "True"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - .:/app
    command: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

volumes:
  postgres_data:
    driver: local
```

---

## 🚀 Docker 배포 명령어

```bash
# 컨테이너 빌드 및 실행
docker-compose up

# 백그라운드 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f app
docker-compose logs -f db

# 컨테이너 중지
docker-compose down

# 데이터 함께 삭제 (주의!)
docker-compose down -v
```

---

**완료 후 체크리스트:**
- [ ] 모든 서비스가 정상 작동
- [ ] 환경변수가 정확히 설정됨
- [ ] 데이터베이스 테이블이 생성됨
- [ ] API 엔드포인트가 응답함
- [ ] .env 파일이 .gitignore에 포함됨
