"""HTML pages render (guards against template API changes in newer Starlette)."""

import asyncio

from arxivbot.services import db, paper_service


def test_home_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<html" in resp.text
    assert 'id="paper-form"' in resp.text
    assert 'id="paper-input"' in resp.text
    assert "/static/paper-form.js" in resp.text
    assert "function goToPaper" not in resp.text


def test_paper_form_script_is_served(client):
    resp = client.get("/static/paper-form.js")
    assert resp.status_code == 200
    assert "function goToPaper" in resp.text


def test_abs_renders_with_metadata(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert "Attention Is All You Need" in resp.text
    assert "status-retry-btn" in resp.text


def test_abs_unknown_paper_returns_404_with_form(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        raise paper_service.PaperNotFound(paper_id)

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/9999.99999")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert "No arXiv paper with ID 9999.99999" in resp.text
    assert 'id="paper-form"' in resp.text
    assert "/static/paper-form.js" in resp.text
    assert 'href="https://arxiv.org/search/"' in resp.text
    assert 'href="/"' in resp.text
    # No chat UI, so nothing starts indexing
    assert "ar5iv-iframe" not in resp.text
    assert "status-retry-btn" not in resp.text


def test_abs_transient_metadata_failure_renders_chat(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return None

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert "status-retry-btn" in resp.text
    assert "1706.03762" in resp.text
    assert asyncio.run(db.get_paper("1706.03762")) is None


def test_abs_persists_metadata(client, monkeypatch):
    calls = []

    async def fetch_paper_metadata(paper_id):
        calls.append(paper_id)
        return {
            "title": "Attention Is All You Need",
            "authors": ["A. Vaswani"],
            "abstract": "We propose the Transformer.",
        }

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    assert client.get("/abs/1706.03762").status_code == 200
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert "Attention Is All You Need" in resp.text
    assert calls == ["1706.03762"]

    # The indexing upsert carries no metadata and must not erase it
    asyncio.run(db.upsert_paper(db.Paper(id="1706.03762")))
    paper = asyncio.run(db.get_paper("1706.03762"))
    assert paper.title == "Attention Is All You Need"
    assert paper.authors == ["A. Vaswani"]
    assert paper.abstract == "We propose the Transformer."


def test_chat_page_survives_paper_not_found(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        raise paper_service.PaperNotFound(paper_id)

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    asyncio.run(db.create_chat("abc123", "1706.03762"))
    resp = client.get("/chat/abc123")
    assert resp.status_code == 200


ATOM_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <opensearch:totalResults>0</opensearch:totalResults>
</feed>"""

ATOM_ENTRY = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Attention Is
 All You Need</title>
    <summary> We propose the Transformer. </summary>
    <author><name>A. Vaswani</name></author>
  </entry>
</feed>"""


def _fake_arxiv_get(monkeypatch, result):
    async def fake_get(url, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(paper_service, "_arxiv_get", fake_get)


def test_fetch_metadata_raises_not_found_for_empty_feed(monkeypatch):
    _fake_arxiv_get(monkeypatch, (200, ATOM_EMPTY))
    try:
        asyncio.run(paper_service.fetch_paper_metadata("9999.99999"))
    except paper_service.PaperNotFound:
        pass
    else:
        raise AssertionError("expected PaperNotFound")


def test_fetch_metadata_returns_none_on_non_200(monkeypatch):
    _fake_arxiv_get(monkeypatch, (503, ""))
    assert asyncio.run(paper_service.fetch_paper_metadata("1706.03762")) is None


def test_fetch_metadata_returns_none_on_exception(monkeypatch):
    _fake_arxiv_get(monkeypatch, TimeoutError("slow"))
    assert asyncio.run(paper_service.fetch_paper_metadata("1706.03762")) is None


def test_fetch_metadata_parses_entry(monkeypatch):
    _fake_arxiv_get(monkeypatch, (200, ATOM_ENTRY))
    meta = asyncio.run(paper_service.fetch_paper_metadata("1706.03762"))
    assert meta == {
        "title": "Attention Is  All You Need",
        "abstract": "We propose the Transformer.",
        "authors": ["A. Vaswani"],
    }


def test_home_github_link_points_at_repo(client):
    html = client.get("/").text
    assert 'href="https://github.com"' not in html
    assert 'href="https://github.com/k7lim/arxivbot.org"' in html


def test_home_example_is_clickable_and_bolds_inserted_letters(client):
    html = client.get("/").text
    assert '<a class="url new" href="/abs/1706.03762">' in html
    assert "https://arxiv<strong>bot</strong>.org/abs/1706.03762" in html
    assert "Add <strong>bot</strong> after <code>arxiv</code> in any arXiv paper URL." in html
    assert "Works with /abs/, /pdf/ and /html/ links." in html
    assert "Simply change" not in html


def test_home_form_label_and_single_main(client):
    html = client.get("/").text
    assert '<label for="paper-input" class="visually-hidden">arXiv ID or URL</label>' in html
    assert html.count("<main>") == 1
    assert html.count("</main>") == 1


def test_error_page_form_has_label(client):
    html = client.get("/nope").text
    assert 'label for="paper-input"' in html


def test_visually_hidden_rule_is_served(client):
    assert ".visually-hidden" in client.get("/static/style.css").text
