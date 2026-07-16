# 서버 배포 순서 (Ubuntu 기준)

## 1. 코드 받기

```bash
git clone https://github.com/KTCloud-Crypto/KTCloud-Crypto.git
cd KTCloud-Crypto
```

## 2. Docker / Docker Compose 설치

```bash
apt update && apt install -y docker.io docker-compose-plugin
```

## 3. .env 파일 생성

```bash
cp .env.example .env
nano .env
```

아래 내용 입력 (`POSTGRES_*`, `DATABASE_URL`, `SERVER_*`는 `.env.example` 값 참고):

```
SECRET_KEY=랜덤한_긴_문자열
MASTER_ENCRYPTION_KEY=파이썬에서_Fernet.generate_key()로_생성한_값
TELEGRAM_BOT_TOKEN=봇토큰 (선택)
```

`MASTER_ENCRYPTION_KEY` 생성:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> 로컬 개발용 키를 그대로 쓰지 말고 서버마다 새로 발급할 것. 유출 시 모든 사용자의 거래소 API Key가 복호화될 수 있음.

## 4. 실행

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

## 5. 트레이딩뷰 웹훅 URL

각 사용자는 회원가입/로그인 후 `GET /users/me/webhook-url`로 자신의 웹훅 URL을 확인해서 사용한다.

```
https://<서버주소>/webhook/{본인 토큰}
```

웹훅 메시지 형식:

```json
{"action": "buy", "ticker": "KRW-BTC"}
{"action": "sell", "ticker": "KRW-BTC"}
```

## 6. 프론트엔드 API 주소 설정

프론트엔드는 기본적으로 `http://localhost:8000`을 백엔드로 바라본다. 실서버 배포 시 `frontend` 서비스에 `VITE_API_BASE_URL` 환경변수로 실제 백엔드 주소를 지정해야 한다 (`docker-compose.yml`의 `frontend.environment`에 추가).

## 로그 확인

```bash
docker compose logs -f backend
docker compose logs -f db
docker compose logs -f frontend
```

## 서버 재시작

```bash
docker compose down
docker compose up --build -d
docker compose logs -f backend
```

> DB 스키마를 변경하는 커밋을 반영할 때는 Alembic이 없으므로, 컬럼/테이블 구조가 바뀌었다면 기존 데이터가 있는 운영 DB에는 수동으로 마이그레이션 SQL을 적용해야 한다. `docker compose down -v`(볼륨 삭제)는 로컬 개발 환경에서만 사용할 것.
