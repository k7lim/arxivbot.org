"""HTML pages render (guards against template API changes in newer Starlette)."""

from arxivbot.services import paper_service


def test_home_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<html" in resp.text


def test_abs_renders_with_metadata(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        return {"title": "Attention Is All You Need", "authors": [], "abstract": ""}

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/1706.03762")
    assert resp.status_code == 200
    assert "Attention Is All You Need" in resp.text
    assert "status-retry-btn" in resp.text
