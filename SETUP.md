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

운영 서버에서는 다음 값도 설정한다.

```dotenv
CORS_ORIGINS=https://signaltrade.kro.kr
ALLOWED_HOSTS=signaltrade.kro.kr,api.signaltrade.kro.kr,localhost,127.0.0.1,backend
VITE_API_BASE_URL=/api
DOMAIN=signaltrade.kro.kr
CERTBOT_EMAIL=실제_이메일
HTTPS_ENABLED=false
```

`CORS_ORIGINS`에 포트가 있으면 포트까지 정확히 적고, 여러 Origin은 쉼표로 구분한다.

## 4. HTTP 실행

```bash
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health
```

백엔드는 외부에 직접 노출되지 않는다. 아래 주소로 Nginx와 API 프록시를 확인한다.

```bash
curl -i http://34.233.225.79/healthz
curl -i http://34.233.225.79/api/health
```

EC2 보안 그룹 인바운드에는 최소한 다음 규칙이 필요하다.

- TCP 80, 소스 `0.0.0.0/0` 및 필요 시 `::/0`
- TCP 443, 소스 `0.0.0.0/0` 및 필요 시 `::/0`
- SSH 22는 관리 IP로 제한

## 5. DNS와 HTTPS

도메인의 A 레코드를 `34.233.225.79`로 지정하고 전파를 확인한다.

```bash
dig +short "$DOMAIN" A
```

결과가 `34.233.225.79`일 때 HTTP-01 인증서를 발급한다.

```bash
docker compose --profile tls run --rm certbot certonly \
  --webroot --webroot-path /var/www/certbot \
  --domain "$DOMAIN" --email "$CERTBOT_EMAIL" \
  --agree-tos --no-eff-email
```

발급 후 `.env`의 `HTTPS_ENABLED=true`로 변경하고 프론트엔드를 재생성한다.

```bash
docker compose up -d --build frontend
curl -I "https://$DOMAIN/"
curl -i "https://$DOMAIN/api/health"
```

인증서 갱신은 다음 명령을 cron 또는 systemd timer에 등록하고, 성공 후 Nginx를 reload한다.

```bash
docker compose --profile tls run --rm certbot renew --webroot -w /var/www/certbot
docker compose exec frontend nginx -s reload
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

프론트엔드 주소는 런타임 환경변수가 아니라 Docker 빌드 인자 `VITE_API_BASE_URL`로 주입된다. 기본값 `/api`는 같은 Origin의 Nginx 프록시를 사용하므로 운영 환경에서도 권장된다. 값을 바꾸면 `docker compose build frontend`가 필요하다.

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
