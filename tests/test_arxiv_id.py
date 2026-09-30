"""Tests for arXiv ID parsing/normalization and canonical-ID routing."""

import pytest

from arxivbot.services import paper_service
from arxivbot.utils.arxiv import extract_arxiv_id_from_path, parse_arxiv_id


@pytest.mark.parametrize(
    "raw, paper_id, base_id, version, category",
    [
        ("1706.03762", "1706.03762", "1706.03762", None, None),
        ("2601.15621v1", "2601.15621v1", "2601.15621", 1, None),
        ("1706.03762V1", "1706.03762v1", "1706.03762", 1, None),
        ("1706.03762v7", "1706.03762v7", "1706.03762", 7, None),
        ("math/9901001", "math/9901001", "math/9901001", None, "math"),
        ("hep-th/9901001v2", "hep-th/9901001v2", "hep-th/9901001", 2, "hep-th"),
        ("math.AG/0211159", "math/0211159", "math/0211159", None, "math"),
        ("math.AG/0211159v2", "math/0211159v2", "math/0211159", 2, "math"),
        ("cs.LG/9901001v2", "cs/9901001v2", "cs/9901001", 2, "cs"),
        ("cs.LG/9901001V2", "cs/9901001v2", "cs/9901001", 2, "cs"),
        ("Math/0211159", "math/0211159", "math/0211159", None, "math"),
        ("HEP-TH/9901001", "hep-th/9901001", "hep-th/9901001", None, "hep-th"),
        ("  1706.03762  ", "1706.03762", "1706.03762", None, None),
    ],
)
def test_parse_valid(raw, paper_id, base_id, version, category):
    parsed = parse_arxiv_id(raw)
    assert parsed is not None
    assert parsed.paper_id == paper_id
    assert parsed.base_id == base_id
    assert parsed.version == version
    assert parsed.category == category


def test_versioned_and_unversioned_stay_distinct():
    assert parse_arxiv_id("1706.03762").paper_id != parse_arxiv_id("1706.03762v7").paper_id


def test_canonical_urls_drop_subject_class():
    parsed = parse_arxiv_id("math.AG/0211159")
    assert parsed.abs_url == "https://arxiv.org/abs/math/0211159"
    assert parsed.src_url == "https://arxiv.org/src/math/0211159"


@pytest.mark.parametrize(
    "raw",
    ["math.AG/021115", "1706.376", "17060.3762", "foo", "", "   ", "math./0211159", "math.AG/02111590", "1706.03762v"],
)
def test_parse_invalid(raw):
    assert parse_arxiv_id(raw) is None


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/abs/math.AG/0211159", "math/0211159"),
        ("/pdf/1706.03762V1.pdf", "1706.03762v1"),
        ("/abs/2601.15621", "2601.15621"),
        ("/abs/foo", None),
    ],
)
def test_extract_from_path_is_canonical(path, expected):
    assert extract_arxiv_id_from_path(path) == expected


@pytest.fixture
def no_network(monkeypatch):
    calls = {"metadata": [], "index": [], "ar5iv": []}

    async def fake_metadata(paper_id):
        calls["metadata"].append(paper_id)
        return {"title": "Stub", "abstract": "", "authors": []}

    async def fake_index(paper_id):
        calls["index"].append(paper_id)
        return ""

    async def fake_ar5iv(paper_id):
        calls["ar5iv"].append(paper_id)
        return "<html><body>ok</body></html>"

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fake_metadata)
    monkeypatch.setattr(paper_service, "index_paper", fake_index)
    monkeypatch.setattr(paper_service, "fetch_ar5iv_html", fake_ar5iv)
    return calls


def test_abs_subject_class_redirects_to_canonical(client, no_network):
    resp = client.get("/abs/math.AG/0211159", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/abs/math/0211159"
    assert no_network["metadata"] == []


def test_abs_uppercase_version_redirects_to_canonical(client, no_network):
    resp = client.get("/abs/1706.03762V1", follow_redirects=False)
    assert resp.status_code == 301
    assert resp.headers["location"] == "/abs/1706.03762v1"


def test_abs_canonical_renders(client, no_network):
    resp = client.get("/abs/math/0211159", follow_redirects=False)
    assert resp.status_code == 200
    assert no_network["metadata"] == ["math/0211159"]


def test_abs_invalid_still_400(client, no_network):
    resp = client.get("/abs/math.AG/021115", follow_redirects=False)
    assert resp.status_code == 400


def test_pdf_and_html_redirect_to_canonical(client, no_network):
    resp = client.get("/pdf/math.AG/0211159v2.pdf", follow_redirects=False)
    assert resp.headers["location"] == "/abs/math/0211159v2"
    resp = client.get("/html/1706.03762V1", follow_redirects=False)
    assert resp.headers["location"] == "/abs/1706.03762v1"


def test_status_uppercase_version_not_400(client, no_network):
    resp = client.get("/api/status/1706.03762V1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_started"
    assert no_network["index"] == []
    resp = client.post("/api/index/1706.03762V1?auto=1")
    assert resp.status_code == 200
    assert no_network["index"] == ["1706.03762v1"]


def test_status_subject_class_uses_canonical_id(client, no_network):
    resp = client.get("/api/status/math.AG/0211159")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_started"
    assert no_network["index"] == []
    resp = client.post("/api/index/math.AG/0211159?auto=1")
    assert resp.status_code == 200
    assert no_network["index"] == ["math/0211159"]


def test_ar5iv_uses_canonical_id(client, no_network):
    resp = client.get("/ar5iv/math.AG/0211159")
    assert resp.status_code == 200
    assert no_network["ar5iv"] == ["math/0211159"]
