"""GET /api/status is read-only; POST /api/index is the only indexing trigger (v2i)."""

import time

import pytest

from arxivbot.services import paper_service

PAPER_ID = "2301.00002"
INDEX_LIMIT = 10


@pytest.fixture(autouse=True)
def clean_state():
    paper_service._indexing_status.clear()
    paper_service._content_cache.clear()
    yield
    paper_service._indexing_status.clear()
    paper_service._content_cache.clear()


@pytest.fixture
def index_calls(monkeypatch):
    """Record index_paper calls instead of hitting arXiv."""
    calls = []

    async def fake_index(paper_id):
        calls.append(paper_id)

    monkeypatch.setattr(paper_service, "index_paper", fake_index)
    return calls


def set_error(age):
    paper_service._indexing_status[PAPER_ID] = {
        "status": "error",
        "error": paper_service.TRANSIENT_ERROR_MESSAGE,
        "error_at": time.time() - age,
    }


def test_get_status_is_read_only(client, index_calls):
    for _ in range(2):
        resp = client.get(f"/api/status/{PAPER_ID}")
        assert resp.status_code == 200
        assert resp.json() == {"status": "not_started", "progress": 0, "error": None}
    assert index_calls == []
    assert PAPER_ID not in paper_service._indexing_status


def test_get_status_does_not_retry_error_after_cooldown(client, index_calls):
    set_error(paper_service.ERROR_RETRY_COOLDOWN + 1)
    resp = client.get(f"/api/status/{PAPER_ID}")
    assert resp.json()["status"] == "error"
    assert index_calls == []


def test_auto_index_starts_when_not_started(client, index_calls):
    resp = client.post(f"/api/index/{PAPER_ID}?auto=1")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Indexing started"}
    assert index_calls == [PAPER_ID]
    assert client.get(f"/api/status/{PAPER_ID}").json()["status"] == "starting"


def test_auto_index_does_not_restart_in_progress(client, index_calls):
    client.post(f"/api/index/{PAPER_ID}?auto=1")
    resp = client.post(f"/api/index/{PAPER_ID}?auto=1")
    assert resp.json() == {"message": "Indexing in progress"}
    assert index_calls == [PAPER_ID]


def test_auto_index_error_within_cooldown_does_not_start(client, index_calls):
    set_error(0)
    resp = client.post(f"/api/index/{PAPER_ID}?auto=1")
    assert resp.status_code == 200
    assert index_calls == []
    assert client.get(f"/api/status/{PAPER_ID}").json()["status"] == "error"


def test_auto_index_error_after_cooldown_starts(client, index_calls):
    set_error(paper_service.ERROR_RETRY_COOLDOWN + 1)
    resp = client.post(f"/api/index/{PAPER_ID}?auto=1")
    assert resp.status_code == 200
    assert index_calls == [PAPER_ID]


def test_manual_index_starts_on_error_within_cooldown(client, index_calls):
    set_error(0)
    resp = client.post(f"/api/index/{PAPER_ID}")
    assert resp.status_code == 200
    assert resp.json() == {"message": "Indexing started"}
    assert index_calls == [PAPER_ID]


def test_index_is_rate_limited(client, index_calls):
    headers = {"Fly-Client-IP": "203.0.113.1"}
    for _ in range(INDEX_LIMIT):
        assert client.post("/api/index/bogus", headers=headers).status_code == 400
    assert client.post("/api/index/bogus", headers=headers).status_code == 429
    other = {"Fly-Client-IP": "203.0.113.2"}
    assert client.post("/api/index/bogus", headers=other).status_code == 400
    assert index_calls == []


def test_abs_page_triggers_indexing_with_auto_post(client, monkeypatch, index_calls):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert "fetch(`/api/index/${paperId}?auto=1`, { method: 'POST' })" in resp.text
    assert index_calls == []
