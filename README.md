# KTCloud-Crypto

## Docker Compose 실행

루트 디렉토리에서 실행합니다.

```bash
docker compose up --build -d
```

## 실행 상태 확인

```bash
docker compose ps
```

정상 상태 예시:

```text
frontend   Up
backend    Up healthy
db         Up healthy
```

## Backend 확인

```bash
curl http://localhost:8000/health
```

정상 응답:

```json
{"status":"ok"}
```

## Database 확인

```bash
docker compose exec db psql -U postgres -d fastapi_db -c '\dt'
```

정상 테이블 예시:

```text
api_key
last_signal
trade_history
user
```

## Frontend 확인

```bash
docker compose logs -f frontend
```

정상 로그 예시:

```text
VITE ready
Local: http://localhost:5173/
```

브라우저에서 접속:

```text
http://localhost:5173
```

## 자주 쓰는 명령어

```bash
# 전체 로그 확인
docker compose logs -f

# backend 로그 확인
docker compose logs -f backend

# db 로그 확인
docker compose logs -f db

# 컨테이너 중지
docker compose down

# 컨테이너와 DB 볼륨까지 삭제
docker compose down -v
```
