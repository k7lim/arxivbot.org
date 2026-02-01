"""API routes for chat functionality."""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from arxivbot.services import chat_service, paper_service
from arxivbot.utils.arxiv import parse_arxiv_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    paper_id: str
    chat_slug: str | None = None
    message: str


class Citation(BaseModel):
    """A citation from the paper."""

    text: str
    page: int | None = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    chat_slug: str
    response: str
    citations: list[Citation] = []


class StatusResponse(BaseModel):
    """Response from status endpoint."""

    status: str
    progress: int
    error: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get a response.

    If chat_slug is None, creates a new chat.
    Otherwise, continues an existing chat.
    """
    # Validate paper ID
    parsed = parse_arxiv_id(request.paper_id)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid arXiv ID: {request.paper_id}")

    # Get or create chat
    chat = None
    if request.chat_slug:
        chat = await chat_service.get_chat_by_slug(request.chat_slug)
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        if chat.paper_id != request.paper_id:
            raise HTTPException(status_code=400, detail="Paper ID mismatch")

    # Get chat history for context
    chat_history = []
    if chat:
        messages = await chat_service.get_messages(chat.id)
        chat_history = [{"role": m.role, "content": m.content} for m in messages]

    # Create new chat if needed
    if not chat:
        chat = await chat_service.create_chat(request.paper_id, request.message)

    # Save user message
    await chat_service.add_message(chat.id, "user", request.message)

    try:
        # Query the paper
        result = await paper_service.query_paper(
            paper_id=request.paper_id,
            question=request.message,
            chat_history=chat_history,
        )

        # Save assistant response
        await chat_service.add_message(chat.id, "assistant", result["answer"])

        return ChatResponse(
            chat_slug=chat.slug,
            response=result["answer"],
            citations=[
                Citation(text=c["text"], page=c.get("page"))
                for c in result.get("citations", [])
            ],
        )

    except Exception as e:
        logger.error(f"Error querying paper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{paper_id:path}", response_model=StatusResponse)
async def get_status(paper_id: str, background_tasks: BackgroundTasks):
    """
    Get the indexing status for a paper.

    Also starts indexing in the background if not started.
    """
    # Validate paper ID
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid arXiv ID: {paper_id}")

    status = await paper_service.get_indexing_status(paper_id)

    # Start indexing in background if not started
    if status["status"] == "not_started":
        background_tasks.add_task(paper_service.index_paper, paper_id)
        status = {"status": "starting", "progress": 5}

    return StatusResponse(
        status=status.get("status", "unknown"),
        progress=status.get("progress", 0),
        error=status.get("error"),
    )


@router.post("/index/{paper_id:path}")
async def start_indexing(paper_id: str, background_tasks: BackgroundTasks):
    """Start indexing a paper in the background."""
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise HTTPException(status_code=400, detail=f"Invalid arXiv ID: {paper_id}")

    status = await paper_service.get_indexing_status(paper_id)

    if status["status"] == "complete":
        return {"message": "Already indexed"}

    if status["status"] not in ("not_started", "error"):
        return {"message": "Indexing in progress"}

    background_tasks.add_task(paper_service.index_paper, paper_id)
    return {"message": "Indexing started"}
