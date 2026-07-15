# KTCloud-Crypto

## Backend Docker 실행

FastAPI 서버와 PostgreSQL DB를 Docker Compose로 함께 실행합니다.

```bash
cd backend
docker compose up --build -d
```

실행 확인:

```bash
docker compose ps
curl http://localhost:8000/health
```

정상 응답:

```json
{"status":"ok"}
```

## 자주 쓰는 명령어

```bash
# 컨테이너 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f app
docker compose logs -f db

# 컨테이너 중지
docker compose down

# 컨테이너와 DB 볼륨까지 삭제
docker compose down -v
```

DB 테이블 확인:

```bash
docker compose exec db psql -U postgres -d fastapi_db -c '\dt'
```
