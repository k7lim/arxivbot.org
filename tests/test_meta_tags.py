"""Link-preview metadata (description, canonical, Open Graph, Twitter card) and favicon."""

import re

import pytest

from arxivbot.services import paper_service

PAPER_ID = "1706.03762"
SITE = "https://arxivbot.org"
HOME_DESCRIPTION = (
    "Add &#34;bot&#34; after &#34;arxiv&#34; in any arXiv paper URL to ask questions "
    "about the paper and get answers quoted from its text."
)


def head(resp):
    return resp.text.split("</head>", 1)[0]


def content(html, key):
    """Raw (still escaped) content attribute of the meta tag named or keyed ``key``."""
    match = re.search(rf'<meta (?:name|property)="{re.escape(key)}" content="([^"]*)">', html)
    assert match, f"no meta tag for {key}"
    return match.group(1)


def canonical(html):
    match = re.search(r'<link rel="canonical" href="([^"]*)">', html)
    return match.group(1) if match else None


@pytest.fixture
def metadata(monkeypatch):
    """Monkeypatch fetch_paper_metadata; returns a setter for the metadata dict."""
    state = {"value": None}

    async def fetch_paper_metadata(paper_id):
        return state["value"]

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)

    def set_metadata(title=None, abstract=None):
        state["value"] = {"title": title, "authors": [], "abstract": abstract}

    return set_metadata


def test_abs_has_link_preview_tags(client, metadata):
    metadata("Attention Is All You Need", "The dominant  sequence\n transduction models.")
    h = head(client.get(f"/abs/{PAPER_ID}"))

    url = f"{SITE}/abs/{PAPER_ID}"
    assert content(h, "og:title") == "Attention Is All You Need"
    assert content(h, "og:description") == "The dominant sequence transduction models."
    assert content(h, "description") == "The dominant sequence transduction models."
    assert content(h, "og:url") == url
    assert canonical(h) == url
    assert content(h, "og:image") == f"{SITE}/static/og.png"
    assert content(h, "og:site_name") == "ArxivBot"
    assert content(h, "og:type") == "website"
    assert content(h, "twitter:card") == "summary"
    assert '<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">' in h


def test_abs_description_truncates_long_abstract(client, metadata):
    metadata("T", "word " * 100)
    description = content(head(client.get(f"/abs/{PAPER_ID}")), "description")
    assert description == ("word " * 40) + "..."
    assert len(description) == 203


def test_abs_escapes_title_and_abstract(client, metadata):
    metadata('A "quoted" <b>title</b> & $x<y$', 'Abstract with "quotes" and <script>')
    h = head(client.get(f"/abs/{PAPER_ID}"))

    # content() only matches up to the first raw quote, so equality proves escaping
    assert content(h, "og:title") == (
        "A &#34;quoted&#34; &lt;b&gt;title&lt;/b&gt; &amp; $x&lt;y$"
    )
    assert content(h, "og:description") == (
        "Abstract with &#34;quotes&#34; and &lt;script&gt;"
    )
    assert "<b>title</b>" not in h
    assert "<script>" not in h


def test_abs_fallbacks_when_metadata_unavailable(client, metadata):
    h = head(client.get(f"/abs/{PAPER_ID}"))

    description = (
        f"Ask questions about arXiv paper {PAPER_ID} and get answers quoted from its text."
    )
    assert content(h, "og:title") == f"arXiv {PAPER_ID}"
    assert content(h, "og:description") == description
    assert content(h, "description") == description
    assert canonical(h) == f"{SITE}/abs/{PAPER_ID}"
    assert 'content=""' not in h


def test_chat_page_metadata_omits_message_text(client, metadata, monkeypatch):
    async def query_paper(paper_id, question, chat_history=None):
        return {"answer": "zebra-answer-text", "citations": []}

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    metadata("Attention Is All You Need", "An abstract.")
    # The slug (and so the canonical URL) is derived from the first question, so
    # the check is on the message text itself, not on every word of it.
    question = "What does the Walrus say, exactly?"
    resp = client.post("/api/chat", json={"paper_id": PAPER_ID, "message": question})
    assert resp.status_code == 200
    slug = resp.json()["chat_slug"]

    resp = client.get(f"/chat/{slug}")
    assert resp.status_code == 200
    h = head(resp)
    assert content(h, "og:title") == "Chat about: Attention Is All You Need"
    assert content(h, "og:description") == "A conversation about this paper on ArxivBot."
    assert content(h, "og:url") == f"{SITE}/chat/{slug}"
    assert canonical(h) == f"{SITE}/chat/{slug}"
    assert question in resp.text  # the chat itself still shows it
    assert question not in h
    assert "zebra-answer-text" not in h


def test_chat_page_title_falls_back_to_arxiv_id(client, metadata, monkeypatch):
    async def query_paper(paper_id, question, chat_history=None):
        return {"answer": "ok", "citations": []}

    monkeypatch.setattr(paper_service, "query_paper", query_paper)
    slug = client.post(
        "/api/chat", json={"paper_id": PAPER_ID, "message": "hi"}
    ).json()["chat_slug"]

    h = head(client.get(f"/chat/{slug}"))
    assert content(h, "og:title") == f"Chat about: arXiv {PAPER_ID}"
    assert 'content=""' not in h


def test_home_metadata(client):
    h = head(client.get("/"))
    assert content(h, "description") == HOME_DESCRIPTION
    assert content(h, "og:description") == HOME_DESCRIPTION
    assert content(h, "og:title") == "ArxivBot - Chat with arXiv Papers"
    assert canonical(h) == f"{SITE}/"
    assert content(h, "og:url") == f"{SITE}/"


def test_error_page_has_no_canonical(client, monkeypatch):
    async def fetch_paper_metadata(paper_id):
        raise paper_service.PaperNotFound(paper_id)

    monkeypatch.setattr(paper_service, "fetch_paper_metadata", fetch_paper_metadata)
    resp = client.get("/abs/9999.99999")
    assert resp.status_code == 404
    h = head(resp)
    assert canonical(h) is None
    assert 'property="og:url"' not in h
    assert content(h, "og:title") == "No arXiv paper with ID 9999.99999"
    assert content(h, "og:image") == f"{SITE}/static/og.png"
    assert 'content=""' not in h


def test_site_url_setting_drives_absolute_urls(client, metadata, monkeypatch):
    from arxivbot import config

    monkeypatch.setattr(config.get_settings(), "site_url", "https://example.test/")
    metadata("T", "A")
    h = head(client.get(f"/abs/{PAPER_ID}"))
    assert canonical(h) == f"https://example.test/abs/{PAPER_ID}"
    assert content(h, "og:image") == "https://example.test/static/og.png"


def test_favicon_and_preview_image_are_served(client):
    ico = client.get("/favicon.ico")
    assert ico.status_code == 200
    assert ico.content[:4] == b"\x00\x00\x01\x00"

    svg = client.get("/static/favicon.svg")
    assert svg.status_code == 200
    assert "rgb(140,21,21)" in svg.text

    png = client.get("/static/og.png")
    assert png.status_code == 200
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
