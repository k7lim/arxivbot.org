"""Page routes for serving HTML pages."""

from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from arxivbot.config import get_settings
from arxivbot.services import chat_service, paper_service
from arxivbot.services.db import Paper, get_paper, upsert_paper
from arxivbot.utils.arxiv import parse_arxiv_id

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/abs/{paper_id:path}", response_class=HTMLResponse)
async def new_chat_page(request: Request, paper_id: str):
    """Render a new chat page for a paper."""
    # Validate paper ID
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid arXiv ID: {paper_id}")

    # Send non-canonical spellings (math.AG/0211159, 1706.03762V1) to the canonical URL
    if parsed.paper_id != paper_id:
        return RedirectResponse(url=f"/abs/{parsed.paper_id}", status_code=301)
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

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "paper_id": paper_id,
            "paper_title": title,
            "paper_url": parsed.abs_url,
            "chat_slug": None,
            "messages": [],
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

    # Get chat messages
    messages = await chat_service.get_messages(chat.id)

    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "paper_id": paper_id,
            "paper_title": title,
            "paper_url": parsed.abs_url,
            "chat_slug": slug,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        },
    )


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Render the home page."""
    return templates.TemplateResponse(
        request,
        "home.html",
    )


def _site_url() -> str:
    """Public origin without a trailing slash."""
    return get_settings().site_url.rstrip("/")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    """Crawler rules: keep bots out of the API and the proxied ar5iv content."""
    return (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Disallow: /ar5iv/\n"
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


AR5IV_ERROR_MARKER ='<meta name="arxivbot-error" content="{kind}">'


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
