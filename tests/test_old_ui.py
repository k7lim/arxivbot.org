"""Pre-redesign UI snapshot under /old, for before/after demos."""

import asyncio
import re

import pytest

from arxivbot.services import chat_service, db, paper_service

PAPER_ID = "1706.03762"


@pytest.fixture
def metadata(monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)


def static_refs(text):
    return re.findall(r'(?:src|href)="(/static/[^"]+\.(?:css|js)[^"]*)"', text)


def assert_old_page(client, text, new_url):
    refs = static_refs(text)
    assert refs and all(r.startswith("/static/old/") for r in refs)
    for ref in refs:
        assert client.get(ref).status_code == 200
    assert '<meta name="robots" content="noindex">' in text
    assert f'class="old-ribbon" href="{new_url}"' in text


def test_old_home(client):
    text = client.get("/old").text
    assert_old_page(client, text, "/")
    assert "Chat with any arXiv paper using AI" in text
    assert "gallery-card" not in text
    assert 'href="/old/abs/1706.03762"' in text
    assert "'/old/abs/'" in client.get("/static/old/paper-form.js").text


def test_old_new_chat_page(client, metadata):
    text = client.get(f"/old/abs/{PAPER_ID}").text
    assert_old_page(client, text, f"/abs/{PAPER_ID}")
    assert '<button type="button" class="starter">Summarize this paper</button>' in text
    assert "level: 'legacy'" in text
    assert "`/old/chat/${chatSlug}`" in text
    assert 'name="level"' not in text


def test_old_paths_canonicalize_under_old(client, metadata):
    resp = client.get(f"/old/abs/{PAPER_ID}V1", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == f"/old/abs/{PAPER_ID}v1"


def test_old_chat_page_shows_saved_chat(client, metadata):
    asyncio.run(db.upsert_paper(db.Paper(id=PAPER_ID)))
    slug = asyncio.run(
        chat_service.save_turn("What is attention?", "A weighting.", paper_id=PAPER_ID)
    )
    text = client.get(f"/old/chat/{slug}").text
    assert_old_page(client, text, f"/chat/{slug}")
    assert "What is attention?" in text and "A weighting." in text
    assert 'id="shared-banner"' not in text
    assert client.get("/old/chat/nope").status_code == 404


def test_robots_keeps_crawlers_off_old(client):
    assert "Disallow: /old" in client.get("/robots.txt").text.splitlines()


def test_legacy_level_uses_the_original_prompt():
    messages = paper_service._build_messages(
        "PAPER {braces}", "q", [{"role": "user", "content": "a"}], level="legacy"
    )
    system = messages[0]["content"]
    assert "<paper>\nPAPER {braces}\n</paper>" in system
    assert "Ask next" not in system and "no research background" not in system
    assert system.endswith("This represents a significant improvement over prior work.")
    assert [m["role"] for m in messages] == ["system", "user", "user"]


def test_api_accepts_legacy_level(client, monkeypatch):
    levels = []

    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        levels.append(level)
        return {"answer": "ok", "citations": []}

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    resp = client.post(
        "/api/chat", json={"paper_id": PAPER_ID, "message": "hi", "level": "legacy"}
    )
    assert resp.status_code == 200
    assert levels == ["legacy"]
