"""Paper service for fetching and indexing arXiv papers using paper-qa."""

import logging
from datetime import datetime
from pathlib import Path

from paperqa import Docs, Settings as PQASettings

from arxivbot.config import get_settings
from arxivbot.services import db
from arxivbot.utils.arxiv import parse_arxiv_id

logger = logging.getLogger(__name__)

# Track indexing status per paper
_indexing_status: dict[str, dict] = {}

# Cache for Docs objects (in-memory, per paper)
_docs_cache: dict[str, Docs] = {}


def _get_pqa_settings() -> PQASettings:
    """Build paper-qa settings from app config."""
    settings = get_settings()

    return PQASettings(
        llm=settings.llm_model,
        summary_llm=settings.llm_model,
        embedding=settings.embedding_model,
    )


async def get_indexing_status(paper_id: str) -> dict:
    """Get the current indexing status for a paper."""
    if paper_id in _indexing_status:
        return _indexing_status[paper_id]

    # Check if already in cache
    if paper_id in _docs_cache:
        return {"status": "complete", "progress": 100}

    # Check if paper exists in database
    paper = await db.get_paper(paper_id)
    if paper and paper.indexed_at:
        return {"status": "complete", "progress": 100}

    return {"status": "not_started", "progress": 0}


async def index_paper(paper_id: str) -> Docs:
    """Index a paper. Updates status as it progresses. Returns Docs instance."""
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise ValueError(f"Invalid arXiv ID: {paper_id}")

    # Return cached docs if available
    if paper_id in _docs_cache:
        logger.info(f"Paper {paper_id} already cached")
        return _docs_cache[paper_id]

    _indexing_status[paper_id] = {"status": "fetching", "progress": 10}

    try:
        # Ensure papers directory exists
        papers_dir = Path("./data/papers")
        papers_dir.mkdir(parents=True, exist_ok=True)

        _indexing_status[paper_id] = {"status": "downloading", "progress": 30}

        # Get paper-qa settings
        pqa_settings = _get_pqa_settings()

        # Create Docs instance and add the paper
        docs = Docs()
        await docs.aadd_url(parsed.pdf_url, settings=pqa_settings)

        _indexing_status[paper_id] = {"status": "embedding", "progress": 70}

        # Cache the docs
        _docs_cache[paper_id] = docs

        # Save paper metadata to database
        paper = db.Paper(
            id=paper_id,
            title=None,
            authors=None,
            abstract=None,
            indexed_at=datetime.now(),
        )
        await db.upsert_paper(paper)

        _indexing_status[paper_id] = {"status": "complete", "progress": 100}
        logger.info(f"Successfully indexed paper {paper_id}")

        return docs

    except Exception as e:
        _indexing_status[paper_id] = {"status": "error", "error": str(e)}
        logger.error(f"Failed to index paper {paper_id}: {e}")
        raise


async def query_paper(
    paper_id: str,
    question: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Query a paper using paper-qa.

    Returns:
        dict with 'answer' and 'citations' keys
    """
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise ValueError(f"Invalid arXiv ID: {paper_id}")

    # Get or create docs
    docs = await index_paper(paper_id)

    # Get paper-qa settings
    pqa_settings = _get_pqa_settings()

    # Build context from chat history if available
    full_question = question
    if chat_history:
        context = "\n".join(
            f"{msg['role'].title()}: {msg['content']}" for msg in chat_history[-6:]
        )
        full_question = f"Previous conversation:\n{context}\n\nNew question: {question}"

    # Query the paper
    session = await docs.aquery(full_question, settings=pqa_settings)

    # Extract citations from the result
    citations = []
    if session.contexts:
        for ctx in session.contexts:
            text_preview = ""
            if hasattr(ctx, "text") and hasattr(ctx.text, "text"):
                text_preview = ctx.text.text[:500]
            elif hasattr(ctx, "context"):
                text_preview = ctx.context[:500]

            page = None
            if hasattr(ctx, "text") and hasattr(ctx.text, "page"):
                page = ctx.text.page

            if text_preview:
                citations.append({"text": text_preview, "page": page})

    return {
        "answer": session.answer,
        "citations": citations,
    }


async def fetch_paper_metadata(paper_id: str) -> dict | None:
    """Fetch paper metadata from arXiv API."""
    import aiohttp
    import xml.etree.ElementTree as ET

    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(parsed.api_url) as response:
                if response.status != 200:
                    return None
                text = await response.text()

        root = ET.fromstring(text)

        # Define namespace
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        entry = root.find("atom:entry", ns)
        if entry is None:
            return None

        title = entry.find("atom:title", ns)
        summary = entry.find("atom:summary", ns)
        authors = entry.findall("atom:author/atom:name", ns)

        return {
            "title": title.text.strip().replace("\n", " ") if title is not None else None,
            "abstract": summary.text.strip() if summary is not None else None,
            "authors": [a.text for a in authors] if authors else [],
        }

    except Exception as e:
        logger.error(f"Failed to fetch metadata for {paper_id}: {e}")
        return None
