"""Page routes for serving HTML pages."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from arxivbot.services import chat_service, paper_service
from arxivbot.services.db import get_paper
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

    # Try to get paper metadata
    paper = await get_paper(paper_id)
    metadata = None

    if not paper or not paper.title:
        # Fetch from arXiv API
        metadata = await paper_service.fetch_paper_metadata(paper_id)

    title = None
    if paper and paper.title:
        title = paper.title
    elif metadata:
        title = metadata.get("title")

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
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

    paper = await get_paper(paper_id)
    metadata = None

    if not paper or not paper.title:
        metadata = await paper_service.fetch_paper_metadata(paper_id)

    title = None
    if paper and paper.title:
        title = paper.title
    elif metadata:
        title = metadata.get("title")

    # Get chat messages
    messages = await chat_service.get_messages(chat.id)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
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
        "home.html",
        {
            "request": request,
        },
    )
