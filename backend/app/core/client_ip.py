from ipaddress import ip_address, ip_network

from fastapi import Request

from app.core.config import settings


def resolve_client_ip(request: Request) -> str | None:
    """신뢰 프록시에서 온 경우에만 전달된 원본 IP를 사용합니다."""
    if not request.client:
        return None
    peer = request.client.host
    try:
        trusted = any(
            ip_address(peer) in ip_network(cidr, strict=False)
            for cidr in settings.trusted_proxy_cidr_list
        )
    except ValueError:
        trusted = False
    if trusted:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded:
            try:
                return str(ip_address(forwarded))
            except ValueError:
                pass
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            try:
                return str(ip_address(real_ip))
            except ValueError:
                pass
    return peer
