"""arXiv paper ID parsing utilities."""

import re
from dataclasses import dataclass


@dataclass
class ArxivPaper:
    """Parsed arXiv paper information."""

    paper_id: str  # Full ID like "2601.15621v1" or "math/9901001"
    base_id: str  # ID without version: "2601.15621" or "math/9901001"
    version: int | None  # Version number if present
    category: str | None  # Category for legacy IDs like "math"

    @property
    def pdf_url(self) -> str:
        """Get the PDF URL for this paper."""
        return f"https://arxiv.org/pdf/{self.paper_id}.pdf"

    @property
    def src_url(self) -> str:
        """Get the TeX source URL for this paper."""
        return f"https://arxiv.org/src/{self.paper_id}"

    @property
    def abs_url(self) -> str:
        """Get the abstract page URL for this paper."""
        return f"https://arxiv.org/abs/{self.paper_id}"

    @property
    def api_url(self) -> str:
        """Get the arXiv API URL for metadata."""
        return f"http://export.arxiv.org/api/query?id_list={self.paper_id}"


# Modern arXiv ID pattern: YYMM.NNNNN or YYMM.NNNNNvN
MODERN_PATTERN = re.compile(r"^(\d{4}\.\d{4,5})(v(\d+))?$")

# Legacy arXiv ID pattern: category/YYMMNNN or category/YYMMNNNvN
LEGACY_PATTERN = re.compile(r"^([a-z-]+)/(\d{7})(v(\d+))?$", re.IGNORECASE)


def parse_arxiv_id(paper_id: str) -> ArxivPaper | None:
    """
    Parse an arXiv paper ID.

    Supports:
    - Modern IDs: 2601.15621, 2601.15621v1
    - Legacy IDs: math/9901001, hep-th/9901001v2

    Returns None if the ID is not valid.
    """
    paper_id = paper_id.strip()

    # Try modern pattern first
    match = MODERN_PATTERN.match(paper_id)
    if match:
        base_id = match.group(1)
        version = int(match.group(3)) if match.group(3) else None
        return ArxivPaper(
            paper_id=paper_id,
            base_id=base_id,
            version=version,
            category=None,
        )

    # Try legacy pattern
    match = LEGACY_PATTERN.match(paper_id)
    if match:
        category = match.group(1).lower()
        number = match.group(2)
        version = int(match.group(4)) if match.group(4) else None
        base_id = f"{category}/{number}"
        return ArxivPaper(
            paper_id=paper_id,
            base_id=base_id,
            version=version,
            category=category,
        )

    return None


def extract_arxiv_id_from_path(path: str) -> str | None:
    """
    Extract an arXiv ID from a URL path.

    Examples:
    - /abs/2601.15621 -> 2601.15621
    - /pdf/2601.15621v1 -> 2601.15621v1
    - /abs/math/9901001 -> math/9901001

    Returns the paper ID string or None if not found.
    """
    # Remove leading slash and common prefixes
    path = path.lstrip("/")
    for prefix in ("abs/", "pdf/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break

    # Remove .pdf extension if present
    if path.endswith(".pdf"):
        path = path[:-4]

    # Validate it's a real arXiv ID
    parsed = parse_arxiv_id(path)
    return parsed.paper_id if parsed else None
