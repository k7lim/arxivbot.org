"""Styled HTML error pages for non-API paths; JSON stays for /api/ (bi9)."""

import pytest

from arxivbot.services import paper_service

FORM = 'id="paper-form"'
SCRIPT = "/static/paper-form.js"
SEARCH_LINK = 'href="https://arxiv.org/search/"'


def is_html(resp):
    return resp.headers["content-type"].startswith("text/html")


def is_json(resp):
    return resp.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("path", ["/list/cs.AI/recent", "/a/someone_1", "/search/", "/nope"])
def test_unknown_path_renders_styled_404(client, path):
    resp = client.get(path)
    assert resp.status_code == 404
    assert is_html(resp)
    assert "Page not found" in resp.text
    assert "ArxivBot works on paper pages." in resp.text
    assert "in a paper URL, or paste an ID below." in resp.text
    # The URL trick example and a way back into the product
    assert "<strong>arxiv</strong>.org" in resp.text
    assert "<strong>arxivbot</strong>.org" in resp.text
    assert FORM in resp.text
    assert SCRIPT in resp.text
    assert 'href="/"' in resp.text
    assert SEARCH_LINK not in resp.text


@pytest.mark.parametrize("path", ["/abs/not-an-id", "/abs/"])
def test_invalid_abs_id_renders_styled_400(client, path):
    resp = client.get(path)
    assert resp.status_code == 400
    assert is_html(resp)
    assert "That does not look like an arXiv ID" in resp.text
    assert FORM in resp.text
    assert SCRIPT in resp.text
    assert "<strong>arxivbot</strong>.org" not in resp.text


def test_invalid_abs_id_is_not_reflected(client):
    resp = client.get("/abs/<script>alert(1)</script>")
    assert resp.status_code == 400
    assert "alert(1)" not in resp.text


def test_unknown_chat_slug_renders_styled_404(client):
    resp = client.get("/chat/nope")
    assert resp.status_code == 404
    assert is_html(resp)
    assert "Page not found" in resp.text
    assert FORM in resp.text


def test_api_unknown_path_stays_json(client):
    resp = client.get("/api/nope", headers={"accept": "text/html"})
    assert resp.status_code == 404
    assert is_json(resp)
    assert resp.json() == {"detail": "Not Found"}


def test_api_invalid_id_stays_json(client):
    resp = client.get("/api/status/not-an-id")
    assert resp.status_code == 400
    assert is_json(resp)
    assert "Invalid arXiv ID" in resp.json()["detail"]


def test_static_missing_file_is_not_styled(client):
    resp = client.get("/static/nope.js")
    assert resp.status_code == 404
    assert FORM not in resp.text


def test_ar5iv_keeps_its_marker_error_page(client):
    resp = client.get("/ar5iv/not-an-id")
    assert resp.status_code == 400
    assert 'name="arxivbot-error"' in resp.text
    assert FORM not in resp.text


def test_method_not_allowed_keeps_status_and_allow_header(client):
    resp = client.post("/")
    assert resp.status_code == 405
    assert is_html(resp)
    assert resp.headers["allow"] == "GET"
    assert FORM in resp.text


def test_nonexistent_paper_page_still_shows_search_link(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        raise paper_service.PaperNotFound(paper_id)

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/9999.99999")
    assert resp.status_code == 404
    assert "No arXiv paper with ID 9999.99999" in resp.text
    assert SEARCH_LINK in resp.text
    assert "Try another paper" in resp.text
