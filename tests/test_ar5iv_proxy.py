"""Tests for the /ar5iv proxy route used by the paper pane iframe."""

from arxivbot.services import paper_service

MARKER = '<meta name="arxivbot-error"'


def _stub_fetch(monkeypatch, result):
    calls = []

    async def fake_fetch(paper_id):
        calls.append(paper_id)
        return result

    monkeypatch.setattr(paper_service, "fetch_ar5iv_html", fake_fetch)
    return calls


def test_unavailable_html_returns_404_html_with_marker(client, monkeypatch):
    _stub_fetch(monkeypatch, None)

    resp = client.get("/ar5iv/2301.00001")

    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")
    assert MARKER in resp.text
    assert 'content="html-unavailable"' in resp.text
    assert 'href="https://arxiv.org/pdf/2301.00001"' in resp.text


def test_unavailable_html_old_style_id_pdf_link(client, monkeypatch):
    _stub_fetch(monkeypatch, None)

    resp = client.get("/ar5iv/hep-th/9901001")

    assert resp.status_code == 404
    assert 'href="https://arxiv.org/pdf/hep-th/9901001"' in resp.text


def test_available_html_returns_200(client, monkeypatch):
    page = "<html><body><h1>Paper</h1></body></html>"
    _stub_fetch(monkeypatch, page)

    resp = client.get("/ar5iv/2301.00001")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == page
    assert MARKER not in resp.text


def test_head_is_not_405(client, monkeypatch):
    _stub_fetch(monkeypatch, "<html><body>ok</body></html>")

    resp = client.head("/ar5iv/2301.00001")

    assert resp.status_code == 200


def test_head_unavailable_returns_404(client, monkeypatch):
    _stub_fetch(monkeypatch, None)

    resp = client.head("/ar5iv/2301.00001")

    assert resp.status_code == 404


def test_invalid_id_returns_400_html_with_marker_and_escapes(client, monkeypatch):
    calls = _stub_fetch(monkeypatch, "<html></html>")

    resp = client.get('/ar5iv/<script>alert("x")</script>')

    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("text/html")
    assert MARKER in resp.text
    assert 'content="invalid-id"' in resp.text
    assert "<script>" not in resp.text
    assert "&lt;script&gt;" in resp.text
    assert calls == []
