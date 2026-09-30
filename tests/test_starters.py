"""Chat landing: orientation line and starter questions (22s)."""

import asyncio
import re

from arxivbot.services import chat_service, db, paper_service

ORIENTATION = (
    "Ask anything about this paper, in your own words. "
    "Answers quote the paper so you can check them."
)
# Lay-reader starters (nf4): plain-language entry points, not reviewer questions
STARTERS = [
    "Explain this paper like I'm new to AI",
    "What's the one big idea?",
    "Why does this matter outside research?",
    "Which terms should I learn first?",
]


def _patch_metadata(monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)


def test_empty_chat_shows_orientation_and_starters(client, monkeypatch):
    _patch_metadata(monkeypatch)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert ORIENTATION in resp.text
    assert "Ask a question about this paper to start the conversation." not in resp.text
    buttons = re.findall(
        r'<button type="button" class="starter">([^<]*)</button>', resp.text
    )
    assert buttons == STARTERS
    assert resp.text.count('class="starter"') == 4


def test_chat_with_history_has_no_starters(client, monkeypatch):
    _patch_metadata(monkeypatch)
    asyncio.run(db.upsert_paper(db.Paper(id="1706.03762")))
    slug = asyncio.run(
        chat_service.save_turn(
            "What is attention?", "A weighting mechanism.", paper_id="1706.03762"
        )
    )
    resp = client.get(f"/chat/{slug}")
    assert resp.status_code == 200
    assert "What is attention?" in resp.text
    assert 'class="starter"' not in resp.text
    assert ORIENTATION not in resp.text
