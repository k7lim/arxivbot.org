"""Integration tests for chat endpoint rate limiting."""

import pytest

LIMIT = 5


def post_chat(client, path, fly_ip, xff=None):
    """POST an invalid paper_id so the request fails after the limiter."""
    headers = {"Fly-Client-IP": fly_ip}
    if xff:
        headers["X-Forwarded-For"] = xff
        headers["X_FORWARDED_FOR"] = xff
    return client.post(path, json={"paper_id": "bogus", "message": "hi"}, headers=headers)


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_spoofed_forwarded_for_does_not_reset_limit(client, path):
    for i in range(LIMIT):
        resp = post_chat(client, path, "203.0.113.1", xff=f"198.51.100.{i}")
        assert resp.status_code == 400
    resp = post_chat(client, path, "203.0.113.1", xff="198.51.100.99")
    assert resp.status_code == 429


@pytest.mark.parametrize("path", ["/api/chat", "/api/chat/stream"])
def test_distinct_fly_client_ips_have_independent_limits(client, path):
    for _ in range(LIMIT):
        assert post_chat(client, path, "203.0.113.1").status_code == 400
    assert post_chat(client, path, "203.0.113.1").status_code == 429
    for _ in range(LIMIT):
        assert post_chat(client, path, "203.0.113.2").status_code == 400
    assert post_chat(client, path, "203.0.113.2").status_code == 429
