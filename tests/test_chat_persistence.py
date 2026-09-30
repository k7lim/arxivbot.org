"""Chat turns are persisted only on success; invalid messages are rejected."""

import json
import sqlite3

import pytest

from arxivbot.services import paper_service

PAPER_ID = "1706.03762"
ENDPOINTS = ["/api/chat", "/api/chat/stream"]


def rows(tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    try:
        chats = conn.execute("SELECT id, slug, paper_id FROM chats").fetchall()
        messages = conn.execute(
            "SELECT chat_id, role, content FROM messages ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    return chats, messages


def sse_events(resp):
    return [
        json.loads(line[len("data: "):])
        for line in resp.text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.fixture
def ok_llm(monkeypatch):
    calls = []

    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        calls.append(chat_history)
        return {"answer": f"answer to {question}", "citations": []}

    async def query_paper_stream(paper_id, question, chat_history=None, level="plain"):
        calls.append(chat_history)
        yield "answer "
        yield f"to {question}"

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    monkeypatch.setattr(paper_service, "query_paper_stream", query_paper_stream)
    return calls


@pytest.fixture
def failing_llm(monkeypatch):
    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        raise RuntimeError("No source available")

    async def query_paper_stream(paper_id, question, chat_history=None, level="plain"):
        yield "partial "
        raise RuntimeError("No source available")

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    monkeypatch.setattr(paper_service, "query_paper_stream", query_paper_stream)


def send(client, path, message, chat_slug=None):
    """Send a turn; return (slug or None, succeeded)."""
    resp = client.post(
        path,
        json={"paper_id": PAPER_ID, "chat_slug": chat_slug, "message": message},
    )
    if path.endswith("/stream"):
        assert resp.status_code == 200
        events = sse_events(resp)
        types = [e["type"] for e in events]
        if "error" in types:
            assert "meta" not in types
            return None, False
        assert types[-2:] == ["meta", "done"]
        return events[-2]["chat_slug"], True
    if resp.status_code != 200:
        return None, False
    return resp.json()["chat_slug"], True


@pytest.mark.parametrize("path", ENDPOINTS)
@pytest.mark.parametrize("message", ["", "   \n\t "])
def test_empty_message_rejected(client, tmp_path, ok_llm, path, message):
    resp = client.post(path, json={"paper_id": PAPER_ID, "message": message})
    assert resp.status_code == 422
    assert rows(tmp_path) == ([], [])
    assert ok_llm == []


@pytest.mark.parametrize("path", ENDPOINTS)
def test_oversized_message_rejected(client, tmp_path, ok_llm, path):
    resp = client.post(path, json={"paper_id": PAPER_ID, "message": "x" * 4001})
    assert resp.status_code == 422
    assert rows(tmp_path) == ([], [])


@pytest.mark.parametrize("path", ENDPOINTS)
def test_failure_on_new_chat_writes_nothing(client, tmp_path, failing_llm, path):
    slug, ok = send(client, path, "What is attention?")
    assert not ok and slug is None
    assert rows(tmp_path) == ([], [])


@pytest.mark.parametrize("path", ENDPOINTS)
def test_success_persists_turn_in_order(client, tmp_path, ok_llm, path):
    slug, ok = send(client, path, "  What is attention?  ")
    assert ok
    chats, messages = rows(tmp_path)
    assert [(c[1], c[2]) for c in chats] == [(slug, PAPER_ID)]
    chat_id = chats[0][0]
    assert messages == [
        (chat_id, "user", "What is attention?"),
        (chat_id, "assistant", "answer to What is attention?"),
    ]
    # Chat page for the emitted slug exists
    assert client.get(f"/chat/{slug}").status_code == 200


@pytest.mark.parametrize("path", ENDPOINTS)
def test_failure_on_existing_chat_adds_nothing_and_retry_is_clean(
    client, tmp_path, ok_llm, monkeypatch, path
):
    slug, ok = send(client, path, "first")
    assert ok
    before = rows(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("LLM down")
        yield  # pragma: no cover - makes this an async generator

    async def boom_plain(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(paper_service, "query_paper", boom_plain)
    monkeypatch.setattr(paper_service, "query_paper_stream", boom)
    assert send(client, path, "second", chat_slug=slug) == (None, False)
    assert rows(tmp_path) == before

    # Retry after recovery: history has no dangling user turn, no duplicates
    calls = []

    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        calls.append(chat_history)
        return {"answer": "second answer", "citations": []}

    async def query_paper_stream(paper_id, question, chat_history=None, level="plain"):
        calls.append(chat_history)
        yield "second answer"

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    monkeypatch.setattr(paper_service, "query_paper_stream", query_paper_stream)
    assert send(client, path, "second", chat_slug=slug) == (slug, True)
    assert calls == [
        [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer to first"},
        ]
    ]
    chats, messages = rows(tmp_path)
    assert len(chats) == 1
    assert [(m[1], m[2]) for m in messages] == [
        ("user", "first"),
        ("assistant", "answer to first"),
        ("user", "second"),
        ("assistant", "second answer"),
    ]


def test_llm_errors_are_not_exposed(client, monkeypatch):
    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        raise RuntimeError("provider said: api_key=sk-secret")

    async def query_paper_stream(paper_id, question, chat_history=None, level="plain"):
        raise RuntimeError("provider said: api_key=sk-secret")
        yield  # pragma: no cover

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    monkeypatch.setattr(paper_service, "query_paper_stream", query_paper_stream)

    resp = client.post("/api/chat", json={"paper_id": PAPER_ID, "message": "hi"})
    assert resp.status_code == 500
    assert "sk-secret" not in resp.text

    resp = client.post("/api/chat/stream", json={"paper_id": PAPER_ID, "message": "hi"})
    (event,) = sse_events(resp)
    assert event["type"] == "error"
    assert "sk-secret" not in event["message"]


def test_fetch_errors_are_shown_to_users(client, monkeypatch):
    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        raise paper_service.PaperFetchError("No source available for 1706.03762")

    monkeypatch.setattr(paper_service, "query_paper", query_paper)

    resp = client.post("/api/chat", json={"paper_id": PAPER_ID, "message": "hi"})
    assert resp.json()["detail"] == "No source available for 1706.03762"
