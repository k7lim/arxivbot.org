"""Paper service for fetching arXiv papers and answering questions via direct context."""

import gzip
import io
import logging
import re
import tarfile
from datetime import datetime

import aiohttp
import litellm

from arxivbot.config import get_settings
from arxivbot.services import db
from arxivbot.utils.arxiv import parse_arxiv_id

logger = logging.getLogger(__name__)

# Track indexing status per paper
_indexing_status: dict[str, dict] = {}

# Cache for paper content (in-memory, per paper)
_content_cache: dict[str, str] = {}

# Cache for ar5iv HTML (in-memory, per paper)
_ar5iv_cache: dict[str, str] = {}

# Maximum content size to prevent OOM (500KB should be plenty for most papers)
MAX_CONTENT_CHARS = 500_000

# Maximum number of papers to cache (LRU-style, oldest evicted first)
MAX_CACHE_SIZE = 5

# Maximum ar5iv HTML cache size
MAX_AR5IV_CACHE_SIZE = 3


def _extract_tex_from_tar(data: bytes) -> str:
    """Extract and concatenate all .tex files from a tar.gz archive."""
    tex_contents = []

    try:
        # Try as tar.gz first
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".tex") and member.isfile():
                    f = tar.extractfile(member)
                    if f:
                        content = f.read().decode("utf-8", errors="replace")
                        tex_contents.append(f"% === {member.name} ===\n{content}")
    except tarfile.ReadError:
        try:
            # Maybe it's just gzipped (single file)
            content = gzip.decompress(data).decode("utf-8", errors="replace")
            tex_contents.append(content)
        except Exception:
            # Maybe it's a plain .tex file
            try:
                content = data.decode("utf-8", errors="replace")
                if "\\documentclass" in content or "\\begin{document}" in content:
                    tex_contents.append(content)
            except Exception:
                pass

    return "\n\n".join(tex_contents)


async def get_indexing_status(paper_id: str) -> dict:
    """Get the current indexing status for a paper."""
    if paper_id in _indexing_status:
        return _indexing_status[paper_id]

    # Check if already in cache
    if paper_id in _content_cache:
        return {"status": "complete", "progress": 100}

    # Check if paper exists in database
    paper = await db.get_paper(paper_id)
    if paper and paper.indexed_at:
        return {"status": "complete", "progress": 100}

    return {"status": "not_started", "progress": 0}


async def fetch_paper_content(paper_id: str) -> str:
    """Fetch TeX source for a paper. Returns the concatenated .tex content."""
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        raise ValueError(f"Invalid arXiv ID: {paper_id}")

    # Return cached content if available
    if paper_id in _content_cache:
        logger.info(f"Paper {paper_id} content cached")
        return _content_cache[paper_id]

    _indexing_status[paper_id] = {"status": "fetching", "progress": 10}

    try:
        _indexing_status[paper_id] = {"status": "downloading", "progress": 30}

        async with aiohttp.ClientSession() as session:
            async with session.get(parsed.src_url, allow_redirects=True) as resp:
                if resp.status == 404:
                    raise ValueError(f"No source available for {paper_id}")
                if resp.status != 200:
                    raise ValueError(f"Failed to fetch source: HTTP {resp.status}")

                data = await resp.read()

        _indexing_status[paper_id] = {"status": "extracting", "progress": 60}

        content = _extract_tex_from_tar(data)
        if not content:
            raise ValueError(f"No .tex files found in source for {paper_id}")

        # Truncate very large papers to prevent OOM
        if len(content) > MAX_CONTENT_CHARS:
            logger.warning(
                f"Paper {paper_id} content truncated from {len(content):,} to {MAX_CONTENT_CHARS:,} chars"
            )
            content = content[:MAX_CONTENT_CHARS] + "\n\n[... content truncated due to size ...]"

        _indexing_status[paper_id] = {"status": "complete", "progress": 100}

        # Cache the content (with size limit to prevent OOM)
        if len(_content_cache) >= MAX_CACHE_SIZE:
            # Evict oldest entry
            oldest_key = next(iter(_content_cache))
            del _content_cache[oldest_key]
            logger.info(f"Evicted paper {oldest_key} from cache")
        _content_cache[paper_id] = content

        # Save paper metadata to database
        paper = db.Paper(
            id=paper_id,
            title=None,
            authors=None,
            abstract=None,
            indexed_at=datetime.now(),
        )
        await db.upsert_paper(paper)

        logger.info(f"Successfully fetched paper {paper_id} ({len(content):,} chars)")
        return content

    except Exception as e:
        _indexing_status[paper_id] = {"status": "error", "error": str(e)}
        logger.error(f"Failed to fetch paper {paper_id}: {e}")
        raise


async def index_paper(paper_id: str) -> str:
    """Alias for fetch_paper_content for API compatibility."""
    return await fetch_paper_content(paper_id)


async def query_paper(
    paper_id: str,
    question: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Query a paper using direct context.

    Returns:
        dict with 'answer' key
    """
    # Get paper content
    content = await fetch_paper_content(paper_id)

    settings = get_settings()

    # Build messages for LLM
    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful research assistant. Answer questions about the following scientific paper based on its LaTeX source.

<paper>
{content}
</paper>

Instructions:
- Answer questions accurately based on the paper content
- When referencing specific text from the paper, quote it using this exact format on its own line:
  > "exact text from the paper"
- Keep quotes concise (under 100 characters when possible)
- Quote the exact wording from the paper, not a paraphrase
- If something isn't in the paper, say so
- Be concise but thorough

Example response format:
The authors propose a novel approach to optimization. As stated in the paper:
> "our method achieves 95% accuracy on the benchmark"
This represents a significant improvement over prior work.""",
        }
    ]

    # Add chat history if available
    if chat_history:
        for msg in chat_history[-10:]:  # Last 10 messages for context
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question
    messages.append({"role": "user", "content": question})

    # Call LLM
    response = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
    )

    return {
        "answer": response.choices[0].message.content,
        "citations": [],  # No citations in direct context mode
    }


async def query_paper_stream(
    paper_id: str,
    question: str,
    chat_history: list[dict] | None = None,
):
    """
    Query a paper using direct context with streaming response.

    Yields:
        str chunks of the response
    """
    # Get paper content
    content = await fetch_paper_content(paper_id)

    settings = get_settings()

    # Build messages for LLM
    messages = [
        {
            "role": "system",
            "content": f"""You are a helpful research assistant. Answer questions about the following scientific paper based on its LaTeX source.

<paper>
{content}
</paper>

Instructions:
- Answer questions accurately based on the paper content
- When referencing specific text from the paper, quote it using this exact format on its own line:
  > "exact text from the paper"
- Keep quotes concise (under 100 characters when possible)
- Quote the exact wording from the paper, not a paraphrase
- If something isn't in the paper, say so
- Be concise but thorough

Example response format:
The authors propose a novel approach to optimization. As stated in the paper:
> "our method achieves 95% accuracy on the benchmark"
This represents a significant improvement over prior work.""",
        }
    ]

    # Add chat history if available
    if chat_history:
        for msg in chat_history[-10:]:  # Last 10 messages for context
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current question
    messages.append({"role": "user", "content": question})

    # Call LLM with streaming
    response = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
        stream=True,
    )

    async for chunk in response:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def fetch_paper_metadata(paper_id: str) -> dict | None:
    """Fetch paper metadata from arXiv API."""
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


async def fetch_ar5iv_html(paper_id: str) -> str | None:
    """
    Fetch arXiv HTML for a paper, rewrite URLs to absolute, and inject bridge script.

    Returns None if HTML is unavailable for this paper.
    """
    parsed = parse_arxiv_id(paper_id)
    if not parsed:
        return None

    # Return cached HTML if available
    if paper_id in _ar5iv_cache:
        logger.info(f"arXiv HTML for {paper_id} served from cache")
        return _ar5iv_cache[paper_id]

    # Use official arXiv HTML (better rendering than ar5iv)
    arxiv_html_url = f"https://arxiv.org/html/{paper_id}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(arxiv_html_url, allow_redirects=True) as resp:
                if resp.status == 404:
                    logger.warning(f"arXiv HTML not available for {paper_id}")
                    return None
                if resp.status != 200:
                    logger.warning(f"arXiv returned HTTP {resp.status} for {paper_id}")
                    return None

                html = await resp.text()

        # Rewrite relative URLs to absolute arXiv URLs
        base_url = "https://arxiv.org"

        # Remove <base> tag as it interferes with our proxy
        html = re.sub(r'<base[^>]*/?>', '', html, flags=re.IGNORECASE)

        # Rewrite href="/..." and src="/..."
        html = re.sub(
            r'(href|src)="(/[^"]*)"',
            rf'\1="{base_url}\2"',
            html,
        )

        # Rewrite url(/...) in inline styles
        html = re.sub(
            r'url\((/[^)]*)\)',
            rf'url({base_url}\1)',
            html,
        )

        # Inject our bridge script before </body>
        bridge_script = """
<script src="/static/ar5iv-bridge.js"></script>
"""
        html = html.replace('</body>', bridge_script + '</body>')

        # Inject highlight CSS in <head>
        highlight_css = """
<style>
.llm-highlight,
.llm-highlight * {
    background: #fff59d !important;
    color: #000 !important;
    outline: 2px solid #ffc107;
    scroll-margin-top: 80px;
}
.llm-highlight-pulse,
.llm-highlight-pulse * {
    animation: llm-pulse 0.5s ease-in-out 2;
}
@keyframes llm-pulse {
    0%, 100% { background: #fff59d !important; color: #000 !important; }
    50% { background: #ffeb3b !important; color: #000 !important; }
}
</style>
"""
        html = html.replace('</head>', highlight_css + '</head>')

        # Cache the HTML
        if len(_ar5iv_cache) >= MAX_AR5IV_CACHE_SIZE:
            oldest_key = next(iter(_ar5iv_cache))
            del _ar5iv_cache[oldest_key]
            logger.info(f"Evicted arXiv HTML for {oldest_key} from cache")
        _ar5iv_cache[paper_id] = html

        logger.info(f"Successfully fetched arXiv HTML for {paper_id} ({len(html):,} bytes)")
        return html

    except Exception as e:
        logger.error(f"Failed to fetch arXiv HTML for {paper_id}: {e}")
        return None
