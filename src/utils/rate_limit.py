"""
Rate limiting con slowapi (almacenamiento en memoria, válido para 1 réplica,
igual que el ConnectionManager del WebSocket).
Respeta X-Forwarded-For cuando hay proxy (nginx) delante.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _client_key(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_key, default_limits=[])
