"""Mobile chat layout: paper pane starts collapsed, single-row header (2vs)."""

import re
from pathlib import Path

from arxivbot.services import paper_service

PAPER_ID = "1706.03762"
STYLE = Path(__file__).resolve().parent.parent / "static" / "style.css"


def _page(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get(f"/abs/{PAPER_ID}")
    assert resp.status_code == 200
    return resp.text


def _media_block(css, query):
    """Return the body of the single `@media (query)` block."""
    starts = [m.end() for m in re.finditer(r"@media\s*\(" + re.escape(query) + r"\)\s*\{", css)]
    assert len(starts) == 1, starts
    depth, i = 1, starts[0]
    while depth:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return css[starts[0]:i - 1]


def _rule(block, selector):
    rules = re.findall(r"(?:^|\}|\*/)\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", block)
    assert len(rules) == 1, (selector, rules)
    return rules[0]


def test_narrow_viewport_collapses_pane_before_paint(client, monkeypatch):
    html = _page(client, monkeypatch)
    # The collapse script sits between the pane markup and <main>, so it runs
    # before the chat is parsed and painted (no flash of the expanded pane).
    between = html[html.index('id="resize-handle"'):html.index("<main")]
    script = re.search(r"<script>(.*?)</script>", between, re.S).group(1)
    assert "matchMedia('(max-width: 768px)').matches" in script
    assert "getElementById('paper-pane').classList.add('collapsed')" in script
    assert "getElementById('resize-handle').classList.add('hidden')" in script
    assert "getElementById('toggle-paper').setAttribute('aria-expanded', 'false')" in script


def test_breakpoint_matches_stylesheet():
    block = _media_block(STYLE.read_text(), "max-width: 768px")
    assert "max-height: 40px" in _rule(block, ".paper-pane.collapsed")


def test_iframe_still_loads_when_collapsed(client, monkeypatch):
    html = _page(client, monkeypatch)
    iframe = re.search(r'<iframe\b[^>]*id="ar5iv-iframe"[^>]*>', html, re.S).group(0)
    assert f'src="/ar5iv/{PAPER_ID}"' in iframe
    assert "loading=" not in iframe


def test_toggle_keeps_class_handle_and_aria_in_step(client, monkeypatch):
    html = _page(client, monkeypatch)
    body = re.search(r"function setPaperCollapsed\(collapsed\) \{(.*?)\n        \}", html, re.S).group(1)
    assert "paperPane.classList.toggle('collapsed', collapsed)" in body
    assert "resizeHandle.classList.toggle('hidden', collapsed)" in body
    assert "togglePaperBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true')" in body
    assert "setPaperCollapsed(!paperPane.classList.contains('collapsed'))" in html


def test_quote_link_click_expands_pane(client, monkeypatch):
    html = _page(client, monkeypatch)
    listener = re.search(
        r"document\.addEventListener\('click', function\(e\) \{(.*?)\}, true\);", html, re.S
    ).group(1)
    assert "closest('.quote-link')" in listener
    assert "setPaperCollapsed(false)" in listener


def test_mobile_header_is_single_row_with_ellipsis():
    block = _media_block(STYLE.read_text(), "max-width: 600px")
    header = _rule(block, ".chat-header")
    assert "flex-direction" not in header
    assert "padding: 0.5rem 0.75rem" in header
    assert "min-width: 0" in _rule(block, ".header-center")
    heading = _rule(block, ".paper-heading")
    assert "text-overflow: ellipsis" in heading
    assert "white-space: nowrap" in heading
    assert "white-space: nowrap" in _rule(block, ".share-btn")
