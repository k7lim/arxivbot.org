"""Rate limiting configuration for API endpoints."""

from slowapi import Limiter
from starlette.requests import Request


def get_identifier(request: Request) -> str:
    """Get the real client IP for rate limiting.

    Uses Fly-Client-IP, which Fly's edge proxy sets (overwriting any
    client-supplied value). Falls back to the socket peer address when
    running outside Fly. X-Forwarded-For is deliberately ignored because
    clients can spoof it.
    """
    fly_ip = request.headers.get("fly-client-ip", "").strip()
    if fly_ip:
        return fly_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# Create limiter instance with IP-based rate limiting
# In-memory storage is fine for single-instance Fly.io deployment
limiter = Limiter(key_func=get_identifier)
