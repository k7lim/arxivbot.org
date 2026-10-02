"""Page routes for serving HTML pages."""

import hashlib
from functools import lru_cache
from html import escape
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.templating import Jinja2Templates

from arxivbot.config import get_settings
from arxivbot.services import chat_service, paper_service
from arxivbot.services.db import Paper, get_paper, upsert_paper
from arxivbot.utils.arxiv import parse_arxiv_id

router = APIRouter()
templates = Jinja2Templates(directory="templates")
STATIC_DIR = Path("static")

META_DESCRIPTION_MAX = 200

# Longest ?ask= question a link can pre-fill into the chat box
ASK_PREFILL_MAX = 500

# Home page example gallery: landmark AI papers, each with a plain-language hook
# and a first question that opens the paper up for a newcomer.
GALLERY = [
    {
        "id": "1706.03762",
        "title": "Attention Is All You Need",
        "hook": "The Transformer: the \"T\" in ChatGPT.",
        "ask": "What is attention, explained without math?",
    },
    {
        "id": "2005.14165",
        "title": "Language Models are Few-Shot Learners",
        "hook": "GPT-3, and why a bigger model could suddenly learn from a few examples.",
        "ask": "What does \"few-shot\" mean, and why was it a surprise?",
    },
    {
        "id": "2203.02155",
        "title": "Training language models to follow instructions with human feedback",
        "hook": "How chatbots learned to be helpful instead of just predicting text.",
        "ask": "How did human feedback change the model's behavior?",
    },
    {
        "id": "2201.11903",
        "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        "hook": "Why asking an AI to \"think step by step\" works.",
        "ask": "Why does showing worked examples make the model reason better?",
    },
    {
        "id": "2001.08361",
        "title": "Scaling Laws for Neural Language Models",
        "hook": "Why AI labs keep building bigger models.",
        "ask": "What are scaling laws, in everyday terms?",
    },
    {
        "id": "2006.11239",
        "title": "Denoising Diffusion Probabilistic Models",
        "hook": "The idea behind AI image generators: turning noise into pictures.",
        "ask": "How can removing noise create a new image?",
    },
    {
        "id": "2005.11401",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "hook": "RAG: letting an AI look things up before it answers.",
        "ask": "Why does looking things up reduce made-up answers?",
    },
    {
        "id": "2212.08073",
        "title": "Constitutional AI: Harmlessness from AI Feedback",
        "hook": "Teaching an AI to follow a written set of principles.",
        "ask": "What is the \"constitution\" and how is it used in training?",
    },
]


def _site_url() -> str:
    """Public origin without a trailing slash."""
    return get_settings().site_url.rstrip("/")


# Read by templates/_meta.html for absolute URLs (og:image)
templates.env.globals["site_url"] = _site_url


@lru_cache
def _static_version(path: str) -> str:
    """Short content hash of a static file, so each deploy's changes bust browser caches."""
    try:
        return hashlib.sha256((STATIC_DIR / path).read_bytes()).hexdigest()[:10]
    except OSError:
        return "0"


def static_url(path: str) -> str:
    """URL of a file in static/, versioned by its content."""
    return f"/static/{path}?v={_static_version(path)}"


templates.env.globals["static_url"] = static_url


def _ask_prefill(request: Request) -> str:
    """The ?ask= question to pre-fill into the chat box, trimmed and bounded."""
    return (request.query_params.get("ask") or "").strip()[:ASK_PREFILL_MAX]


def _abstract_description(abstract: str | None) -> str | None:
    """Abstract as a one-line meta description, or None if there is no abstract."""
    text = " ".join((abstract or "").split())
    if not text:
        return None
    if len(text) > META_DESCRIPTION_MAX:
        text = text[:META_DESCRIPTION_MAX] + "..."
    return text


# The UI as it was before the shapeof.ai pass (nf4) lives under /old, with its
# own templates/old and static/old, for before/after demos. Same data and API.
OLD_PREFIX = "/old"


def _template(name: str, prefix: str) -> str:
    return f"old/{name}" if prefix == OLD_PREFIX else name


@router.get("/abs/{paper_id:path}", response_class=HTMLResponse)
async def new_chat_page(request: Request, paper_id: str):
    """Render a new chat page for a paper."""
    return await _new_chat_page(request, paper_id, prefix="")


@router.get("/old/abs/{paper_id:path}", response_class=HTMLResponse)
async def old_new_chat_page(request: Request, paper_id: str):
    """New chat page in the pre-redesign UI."""
    return await _new_chat_page(request, paper_id, prefix=OLD_PREFIX)


async def _new_chat_page(request: Request, paper_id: str, prefix: str):
    # Validate paper ID
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid arXiv ID: {paper_id}")

    # Send non-canonical spellings (math.AG/0211159, 1706.03762V1) to the canonical URL
    if parsed.paper_id != paper_id:
        return RedirectResponse(url=f"{prefix}/abs/{parsed.paper_id}", status_code=301)
    paper_id = parsed.paper_id

    # Try to get paper metadata
    paper = await get_paper(paper_id)
    metadata = None

    if not paper or not paper.title:
        # Fetch from arXiv API
        try:
            metadata = await paper_service.fetch_paper_metadata(paper_id)
        except paper_service.PaperNotFound:
            return templates.TemplateResponse(
                request,
                "error.html",
                {
                    "status_code": 404,
                    "heading": f"No arXiv paper with ID {paper_id}",
                    "message": "Check the ID for typos, or look the paper up on arXiv.",
                },
                status_code=404,
            )
        if metadata:
            # Store it so later views skip the arXiv API
            await upsert_paper(
                Paper(
                    id=paper_id,
                    title=metadata.get("title"),
                    authors=metadata.get("authors"),
                    abstract=metadata.get("abstract"),
                    indexed_at=paper.indexed_at if paper else None,
                )
            )

    title = None
    if paper and paper.title:
        title = paper.title
    elif metadata:
        title = metadata.get("title")
    abstract = (paper.abstract if paper else None) or (metadata or {}).get("abstract")

    return templates.TemplateResponse(
        request,
        _template("chat.html", prefix),
        {
            "paper_id": paper_id,
            "paper_title": title,
            "paper_abstract": abstract,
            "paper_url": parsed.abs_url,
            "new_url": f"/abs/{paper_id}",
            "chat_slug": None,
            "messages": [],
            "ask": _ask_prefill(request),
            "meta_title": title or f"arXiv {paper_id}",
            "meta_description": _abstract_description(abstract)
            or f"Ask questions about arXiv paper {paper_id} and get answers quoted from its text.",
            "meta_canonical": f"{_site_url()}/abs/{paper_id}",
        },
    )


@router.get("/pdf/{paper_id:path}")
async def pdf_redirect(paper_id: str):
    """Redirect /pdf/ URLs to /abs/ for the chat interface."""
    # Remove .pdf extension if present
    if paper_id.endswith(".pdf"):
        paper_id = paper_id[:-4]
    parsed = parse_arxiv_id(paper_id)
    if parsed:
        paper_id = parsed.paper_id
    return RedirectResponse(url=f"/abs/{paper_id}", status_code=302)


@router.get("/html/{paper_id:path}")
async def html_redirect(paper_id: str):
    """Redirect /html/ URLs to /abs/ for the chat interface."""
    parsed = parse_arxiv_id(paper_id)
    if parsed:
        paper_id = parsed.paper_id
    return RedirectResponse(url=f"/abs/{paper_id}", status_code=302)


@router.get("/chat/{slug}", response_class=HTMLResponse)
async def load_chat_page(request: Request, slug: str):
    """Load an existing chat by its slug."""
    return await _load_chat_page(request, slug, prefix="")


@router.get("/old/chat/{slug}", response_class=HTMLResponse)
async def old_load_chat_page(request: Request, slug: str):
    """An existing chat in the pre-redesign UI."""
    return await _load_chat_page(request, slug, prefix=OLD_PREFIX)


async def _load_chat_page(request: Request, slug: str, prefix: str):
    chat = await chat_service.get_chat_by_slug(slug)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Get paper info
    paper_id = chat.paper_id
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise HTTPException(status_code=500, detail="Invalid paper ID in chat")
    paper_id = parsed.paper_id

    paper = await get_paper(paper_id)
    metadata = None

    if not paper or not paper.title:
        try:
            metadata = await paper_service.fetch_paper_metadata(paper_id)
        except paper_service.PaperNotFound:
            metadata = None

    title = None
    if paper and paper.title:
        title = paper.title
    elif metadata:
        title = metadata.get("title")
    abstract = (paper.abstract if paper else None) or (metadata or {}).get("abstract")

    # Get chat messages
    messages = await chat_service.get_messages(chat.id)

    return templates.TemplateResponse(
        request,
        _template("chat.html", prefix),
        {
            "paper_id": paper_id,
            "paper_title": title,
            "paper_abstract": abstract,
            "paper_url": parsed.abs_url,
            "new_url": f"/chat/{slug}",
            "chat_slug": slug,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "ask": _ask_prefill(request),
            # No question or message text here: chats are shared by link only
            "meta_title": f"Chat about: {title or f'arXiv {paper_id}'}",
            "meta_description": "A conversation about this paper on ArxivBot.",
            "meta_canonical": f"{_site_url()}/chat/{slug}",
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Render the home page."""
    return templates.TemplateResponse(
        request,
        "home.html",
        {"meta_canonical": f"{_site_url()}/", "gallery": GALLERY},
    )


@router.get("/old", response_class=HTMLResponse)
async def old_home_page(request: Request):
    """The home page in the pre-redesign UI."""
    return templates.TemplateResponse(
        request,
        _template("home.html", OLD_PREFIX),
        {"meta_canonical": f"{_site_url()}/", "new_url": "/"},
    )


@router.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    """Serve the favicon at the root path browsers request by default."""
    return FileResponse("static/favicon.ico", media_type="image/x-icon")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    """Crawler rules: keep bots out of the API and the proxied ar5iv content."""
    return (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Disallow: /ar5iv/\n"
        "Disallow: /old\n"
        f"Sitemap: {_site_url()}/sitemap.xml\n"
    )


@router.get("/sitemap.xml")
async def sitemap_xml():
    """Sitemap listing only the home page (chats are link-shared, not published)."""
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{escape(_site_url())}/</loc></url>\n"
        "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    """Markdown summary of the site for LLM crawlers."""
    return (
        "# ArxivBot\n"
        "\n"
        'Chat with any arXiv paper. Add "bot" after "arxiv" in a paper URL.\n'
        "\n"
        "## Supported URL forms\n"
        "\n"
        "- `/abs/<id>`: chat with the paper that has this arXiv ID\n"
        "- `/pdf/<id>`: redirects to `/abs/<id>`\n"
        "- `/html/<id>`: redirects to `/abs/<id>`\n"
        "- `/chat/<slug>`: a saved chat, shared by link\n"
    )


AR5IV_ERROR_MARKER = '<meta name="arxivbot-error" content="{kind}">'


def _ar5iv_error_page(status_code: int, kind: str, message: str, paper_id: str) -> HTMLResponse:
    """Small HTML error page for the paper iframe, tagged with a marker the parent detects."""
    pdf_url = escape(f"https://arxiv.org/pdf/{paper_id}", quote=True)
    body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{AR5IV_ERROR_MARKER.format(kind=kind)}
<title>Paper unavailable</title>
</head>
<body>
<p>{escape(message)}</p>
<p><a href="{pdf_url}" target="_blank" rel="noopener">View PDF on arXiv</a></p>
</body>
</html>
"""
    return HTMLResponse(content=body, status_code=status_code)


@router.api_route("/ar5iv/{paper_id:path}", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def ar5iv_proxy(paper_id: str):
    """
    Proxy ar5iv HTML through our server.

    This solves cross-origin issues and allows us to inject our bridge script.
    Error responses are small HTML pages carrying an ``arxivbot-error`` meta
    marker so the parent page can detect them from the iframe's load event.
    """
    # Validate paper ID
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        return _ar5iv_error_page(
            400, "invalid-id", f"Invalid arXiv ID: {paper_id}", paper_id
        )
    paper_id = parsed.paper_id

    # Fetch (or get cached) ar5iv HTML
    html = await paper_service.fetch_ar5iv_html(paper_id)

    if html is None:
        return _ar5iv_error_page(
            404,
            "html-unavailable",
            f"HTML view unavailable for paper {paper_id}.",
            paper_id,
        )

    return HTMLResponse(content=html)
