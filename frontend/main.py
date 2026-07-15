import hashlib
import hmac
import time
import uuid
import urllib.parse
import requests

def check_upbit_connection(access_key: str, secret_key: str) -> None:
    # JWT 토큰 생성
    try:
        import jwt
    except ImportError:
        print("[오류] PyJWT 라이브러리가 없습니다. 설치 후 다시 실행하세요:")
        print("  pip install PyJWT requests")
        return

    payload = {
        "access_key": access_key,
        "nonce": str(uuid.uuid4()),
    }

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            "https://api.upbit.com/v1/accounts",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            accounts = response.json()
            print(f"\n[성공] 업비트 API 연결 확인됨")
            print(f"보유 자산 수: {len(accounts)}개")
            print("-" * 40)
            for acc in accounts:
                currency = acc.get("currency", "")
                balance = float(acc.get("balance", 0))
                locked = float(acc.get("locked", 0))
                if balance > 0 or locked > 0:
                    print(f"  {currency}: {balance:.8f} (거래중: {locked:.8f})")
        elif response.status_code == 401:
            print(f"\n[실패] 인증 오류 (401) - API 키를 확인하세요")
            print(f"상세: {response.json().get('error', {}).get('message', '')}")
        else:
            print(f"\n[실패] HTTP {response.status_code}")
            print(f"응답: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n[오류] 네트워크 연결 실패")
    except requests.exceptions.Timeout:
        print("\n[오류] 요청 시간 초과")


if __name__ == "__main__":
    print("=== 업비트 API 연결 확인 ===")
    access_key = input("Access Key: ").strip()
    secret_key = input("Secret Key: ").strip()

    if not access_key or not secret_key:
        print("[오류] 키를 입력하세요")
    else:
        check_upbit_connection(access_key, secret_key)