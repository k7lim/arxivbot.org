"""Rate limiting configuration for API endpoints."""

from slowapi import Limiter
from slowapi.util import get_ipaddr


def get_identifier(request):
    """Get client IP address from request.

    Uses get_ipaddr which respects X-Forwarded-For header,
    necessary for deployments behind proxies like Fly.io.
    """
    return get_ipaddr(request)


# Create limiter instance with IP-based rate limiting
# In-memory storage is fine for single-instance Fly.io deployment
limiter = Limiter(key_func=get_identifier)
