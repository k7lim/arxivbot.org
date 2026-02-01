"""Chat service for managing conversations."""

import re
import uuid

from arxivbot.services import db


def generate_chat_slug(first_message: str) -> str:
    """
    Generate a URL-friendly slug from the first message.

    Format: {slugified-message}-{8-char-uuid}
    Example: "What is the main contribution?" -> "what-is-the-main-contribution-a1b2c3d4"
    """
    # Slugify: lowercase, replace non-alphanum with dash
    slug = re.sub(r"[^a-z0-9]+", "-", first_message.lower())
    # Remove leading/trailing dashes and truncate
    slug = slug.strip("-")[:50]
    # Ensure we have something
    if not slug:
        slug = "chat"
    # Append 8-char UUID for uniqueness
    short_uuid = uuid.uuid4().hex[:8]
    return f"{slug}-{short_uuid}"


async def create_chat(paper_id: str, first_message: str) -> db.Chat:
    """Create a new chat for a paper."""
    slug = generate_chat_slug(first_message)
    return await db.create_chat(slug=slug, paper_id=paper_id)


async def get_chat_by_slug(slug: str) -> db.Chat | None:
    """Get a chat by its slug."""
    return await db.get_chat_by_slug(slug)


async def get_chat_by_id(chat_id: int) -> db.Chat | None:
    """Get a chat by its ID."""
    return await db.get_chat_by_id(chat_id)


async def add_message(chat_id: int, role: str, content: str) -> db.Message:
    """Add a message to a chat."""
    return await db.add_message(chat_id=chat_id, role=role, content=content)


async def get_messages(chat_id: int) -> list[db.Message]:
    """Get all messages for a chat."""
    return await db.get_messages(chat_id)
