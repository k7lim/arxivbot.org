"""Lay-reader UX pass (nf4): gallery, ?ask= prefill, answer levels, forks and follow-ups."""

import asyncio
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from arxivbot.routes import pages
from arxivbot.services import chat_service, db, paper_service

from test_chat_persistence import ENDPOINTS, PAPER_ID, rows, sse_events

STATIC = Path(__file__).resolve().parent.parent / "static"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.fixture
def metadata(monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)


@pytest.fixture
def recording_llm(monkeypatch):
    """Fake LLM that records each call's (question, history, level)."""
    calls = []

    async def query_paper(paper_id, question, chat_history=None, level="plain"):
        calls.append((question, chat_history, level))
        return {"answer": f"answer to {question}", "citations": []}

    async def query_paper_stream(paper_id, question, chat_history=None, level="plain"):
        calls.append((question, chat_history, level))
        yield f"answer to {question}"

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    monkeypatch.setattr(paper_service, "query_paper_stream", query_paper_stream)
    return calls


def post(client, path, **body):
    resp = client.post(path, json={"paper_id": PAPER_ID, **body})
    if path.endswith("/stream"):
        events = sse_events(resp)
        meta = [e for e in events if e["type"] == "meta"]
        return meta[0]["chat_slug"] if meta else None
    return resp.json().get("chat_slug")


# Home page: initial CTA, example gallery, randomize


def test_home_leads_with_the_paper_form_and_a_gallery(client):
    text = client.get("/").text
    hero = text[text.index('class="hero"') : text.index('class="gallery"')]
    assert 'id="paper-form"' in hero
    assert 'id="surprise-btn"' in text
    links = re.findall(r'class="gallery-card" href="([^"]+)"', text)
    assert len(links) == len(pages.GALLERY) >= 6
    for link, paper in zip(links, pages.GALLERY):
        assert link.startswith(f"/abs/{paper['id']}?ask=")


# Chat page: ?ask= prefill, anchors, shared banner, level toggle


def test_ask_param_prefills_the_chat_box(client, metadata):
    question = 'What is <b>attention</b> & "why"?'
    text = client.get("/abs/1706.03762", params={"ask": question}).text
    box = re.search(r'<textarea[^>]*id="message-input"[^>]*>([^<]*)</textarea>', text)
    assert box and html.unescape(box.group(1)) == question


def test_ask_prefill_is_bounded(client, metadata):
    text = client.get("/abs/1706.03762", params={"ask": "x" * 5000}).text
    assert "x" * pages.ASK_PREFILL_MAX in text
    assert "x" * (pages.ASK_PREFILL_MAX + 1) not in text


def test_new_chat_page_has_level_toggle_caveat_and_no_shared_banner(client, metadata):
    text = client.get("/abs/1706.03762").text
    assert 'name="level" value="plain" checked' in text
    assert 'name="level" value="technical"' in text
    assert "AI answers can be wrong" in text
    assert 'id="shared-banner"' not in text


def test_saved_chat_has_message_anchors_and_shared_banner(client, metadata):
    asyncio.run(db.upsert_paper(db.Paper(id=PAPER_ID)))
    slug = asyncio.run(
        chat_service.save_turn("What is attention?", "A weighting.", paper_id=PAPER_ID)
    )
    text = client.get(f"/chat/{slug}").text
    assert 'class="message user" id="m-0"' in text
    assert 'class="message assistant" id="m-1"' in text
    # Rendered hidden; the page shows it only to people who did not start the chat
    assert re.search(r'id="shared-banner"[^>]*hidden', text)
    assert "persistedCount = 2;" in text


# API: answer level


@pytest.mark.parametrize("path", ENDPOINTS)
def test_level_defaults_to_plain_and_is_passed_through(client, recording_llm, path):
    post(client, path, message="one")
    post(client, path, message="two", level="technical")
    assert [c[2] for c in recording_llm] == ["plain", "technical"]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_unknown_level_rejected(client, tmp_path, recording_llm, path):
    resp = client.post(path, json={"paper_id": PAPER_ID, "message": "hi", "level": "eli5"})
    assert resp.status_code == 422
    assert recording_llm == []


def test_prompt_pitches_answer_by_level_and_asks_for_follow_ups():
    plain = paper_service._build_messages("PAPER", "q")[0]["content"]
    technical = paper_service._build_messages("PAPER", "q", level="technical")[0]["content"]
    assert "no research background" in plain and "no research background" not in technical
    assert "comfortable with the field" in technical
    for prompt in (plain, technical):
        assert paper_service.FOLLOW_UP_HEADING in prompt
        assert "exactly three" in prompt


# API: forking someone else's shared chat


@pytest.mark.parametrize("path", ENDPOINTS)
def test_fork_copies_history_into_a_new_chat_and_leaves_original(
    client, tmp_path, recording_llm, path
):
    original = post(client, path, message="first")
    before_chats, before_messages = rows(tmp_path)

    fork = post(client, path, message="my own question", chat_slug=original, fork=True)
    assert fork and fork != original

    chats, messages = rows(tmp_path)
    by_slug = {c[1]: c[0] for c in chats}
    assert set(by_slug) == {original, fork}
    original_msgs = [(m[1], m[2]) for m in messages if m[0] == by_slug[original]]
    fork_msgs = [(m[1], m[2]) for m in messages if m[0] == by_slug[fork]]
    assert original_msgs == [(m[1], m[2]) for m in before_messages]
    assert fork_msgs == original_msgs + [
        ("user", "my own question"),
        ("assistant", "answer to my own question"),
    ]
    # The model saw the shared history
    assert recording_llm[-1][1] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer to first"},
    ]
    # Continuing the fork appends to it, not to the original
    assert post(client, path, message="again", chat_slug=fork) == fork
    _, after = rows(tmp_path)
    assert len([m for m in after if m[0] == by_slug[original]]) == 2


@pytest.mark.parametrize("path", ENDPOINTS)
def test_failed_fork_writes_nothing(client, tmp_path, recording_llm, monkeypatch, path):
    original = post(client, path, message="first")
    before = rows(tmp_path)

    async def boom(*args, **kwargs):
        raise RuntimeError("LLM down")
        yield  # pragma: no cover

    async def boom_plain(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(paper_service, "query_paper", boom_plain)
    monkeypatch.setattr(paper_service, "query_paper_stream", boom)
    assert post(client, path, message="x", chat_slug=original, fork=True) is None
    assert rows(tmp_path) == before


# static/followups.js


_SCRIPT = """
const f = require(process.argv[1]);
const inputs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(inputs.map((t) => f.splitFollowUps(t))));
"""


def split_all(texts):
    result = subprocess.run(
        [NODE, "-e", _SCRIPT, str(STATIC / "followups.js")],
        input=json.dumps(texts),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


@needs_node
def test_split_follow_ups():
    full, partial, none, plain_heading, numbered = split_all(
        [
            "Answer.\n> \"quote\"\n\n**Ask next:**\n- What is a head?\n- Why softmax?\n- **RNNs?**\n",
            "Answer.\n\n**Ask next:**\n- What is",
            "Just an answer.\n- a list\n",
            "Answer\nAsk next:\n* One?\n* Two?\n* Three?\n* Four?",
            "Answer\n\n**Ask next**\n1. One?\n2) Two?",
        ]
    )
    assert full == {
        "body": "Answer.\n> \"quote\"",
        "questions": ["What is a head?", "Why softmax?", "RNNs?"],
    }
    assert partial == {"body": "Answer.", "questions": ["What is"]}
    assert none == {"body": "Just an answer.\n- a list\n", "questions": []}
    assert plain_heading == {"body": "Answer", "questions": ["One?", "Two?", "Three?"]}
    assert numbered["questions"] == ["One?", "Two?"]


# Static assets carry a content hash so a deploy's CSS/JS changes reach returning visitors


def test_static_assets_are_versioned_by_content(client, metadata):
    import hashlib

    for url in ("/", "/abs/1706.03762"):
        text = client.get(url).text
        refs = re.findall(r'(?:src|href)="/static/([\w.-]+\.(?:css|js))(\?v=[0-9a-f]+)?"', text)
        assert refs
        for name, version in refs:
            digest = hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:10]
            assert version == f"?v={digest}", name
            assert client.get(f"/static/{name}{version}").status_code == 200
