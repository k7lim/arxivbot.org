"""Tests for rate limiter client identification."""

from starlette.requests import Request

from arxivbot.limiter import get_identifier


def make_request(headers=None, client=("10.0.0.1", 12345)):
    """Build a bare Starlette request with the given headers and peer."""
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/chat",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": client,
    }
    return Request(scope)


def test_uses_fly_client_ip():
    req = make_request({"Fly-Client-IP": "203.0.113.7"})
    assert get_identifier(req) == "203.0.113.7"


def test_falls_back_to_client_host():
    assert get_identifier(make_request()) == "10.0.0.1"


def test_blank_fly_client_ip_falls_back():
    assert get_identifier(make_request({"Fly-Client-IP": "  "})) == "10.0.0.1"


def test_ignores_x_forwarded_for_variants():
    req = make_request(
        {"X-Forwarded-For": "1.2.3.4", "X_FORWARDED_FOR": "5.6.7.8"}
    )
    assert get_identifier(req) == "10.0.0.1"


def test_fly_client_ip_wins_over_x_forwarded_for():
    req = make_request(
        {"Fly-Client-IP": "203.0.113.7", "X-Forwarded-For": "1.2.3.4"}
    )
    assert get_identifier(req) == "203.0.113.7"


def test_no_client_does_not_crash():
    assert get_identifier(make_request(client=None)) == "127.0.0.1"
