"""Chat page accessibility: iframe title, h1, landmarks (7gz)."""

import re

from arxivbot.services import paper_service

TITLE = "Attention Is All You Need"
PAPER_ID = "1706.03762"


def _patch_metadata(monkeypatch, title=TITLE):
    async def fetch_paper_metadata(paper_id):
        return {"title": title, "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)


def _get(client):
    resp = client.get(f"/abs/{PAPER_ID}")
    assert resp.status_code == 200
    return resp.text


def _tag(html, pattern):
    """Return the single opening tag matching pattern."""
    tags = re.findall(pattern, html, re.S)
    assert len(tags) == 1, tags
    return tags[0]


def _h1(html):
    h1s = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.S)
    assert len(h1s) == 1
    return h1s[0]


def test_iframe_has_title(client, monkeypatch):
    _patch_metadata(monkeypatch)
    iframe = _tag(_get(client), r'<iframe\b[^>]*id="ar5iv-iframe"[^>]*>')
    assert f'title="Paper: {TITLE}"' in iframe


def test_exactly_one_h1_with_paper_title(client, monkeypatch):
    _patch_metadata(monkeypatch)
    h1 = _h1(_get(client))
    assert TITLE in h1
    assert 'class="paper-link"' in h1


def test_h1_keeps_80_char_truncation(client, monkeypatch):
    _patch_metadata(monkeypatch, title="A" * 100)
    h1 = _h1(_get(client))
    assert "A" * 80 + "..." in h1
    assert "A" * 81 not in h1


def test_landmarks(client, monkeypatch):
    _patch_metadata(monkeypatch)
    html = _get(client)
    assert len(re.findall(r"<main\b", html)) == 1
    assert html.count("</main>") == 1
    assert 'class="chat-pane"' in _tag(html, r"<main\b[^>]*>")
    aside = _tag(html, r"<aside\b[^>]*>")
    assert 'aria-label="Paper"' in aside
    assert 'id="paper-pane"' in aside
    assert html.count("</aside>") == 1
    # The message list keeps its class and id but is no longer a landmark.
    assert '<div class="chat-messages" id="messages">' in html


def test_toggle_button_is_labelled_and_exposes_state(client, monkeypatch):
    _patch_metadata(monkeypatch)
    html = _get(client)
    button = _tag(html, r'<button\b[^>]*id="toggle-paper"[^>]*>')
    assert 'aria-label="Toggle paper viewer"' in button
    assert 'aria-expanded="true"' in button
    assert "togglePaperBtn.setAttribute('aria-expanded'" in html


def test_no_title_falls_back_to_paper_id(client, monkeypatch):
    _patch_metadata(monkeypatch, title=None)
    html = _get(client)
    assert PAPER_ID in _h1(html)
    iframe = _tag(html, r'<iframe\b[^>]*id="ar5iv-iframe"[^>]*>')
    assert f'title="Paper: {PAPER_ID}"' in iframe
