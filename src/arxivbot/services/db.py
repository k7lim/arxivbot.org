"""SQLite database for papers, chats, and messages."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite

DATABASE_PATH = Path("./data/arxivbot.db")

SCHEMA = """
-- Papers (cached metadata)
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,          -- arxiv ID: "2601.15621v1"
    title TEXT,
    authors TEXT,                 -- JSON array
    abstract TEXT,
    indexed_at TIMESTAMP
);

-- Chats (shareable)
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,    -- "what-is-main-a1b2c3d4"
    paper_id TEXT NOT NULL,       -- FK to papers
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,           -- "user" or "assistant"
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (chat_id) REFERENCES chats(id)
);

CREATE INDEX IF NOT EXISTS idx_chats_slug ON chats(slug);
CREATE INDEX IF NOT EXISTS idx_chats_paper ON chats(paper_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
"""


@dataclass
class Paper:
    id: str
    title: str | None = None
    authors: list[str] | None = None
    abstract: str | None = None
    indexed_at: datetime | None = None


@dataclass
class Chat:
    id: int
    slug: str
    paper_id: str
    created_at: datetime


@dataclass
class Message:
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime


async def init_db(db_path: Path | None = None) -> None:
    """Initialize the database with schema."""
    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_connection(db_path: Path | None = None) -> aiosqlite.Connection:
    """Get a database connection."""
    path = db_path or DATABASE_PATH
    return await aiosqlite.connect(path)


# Paper operations
async def get_paper(paper_id: str, db_path: Path | None = None) -> Paper | None:
    """Get a paper by ID."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Paper(
                    id=row["id"],
                    title=row["title"],
                    authors=json.loads(row["authors"]) if row["authors"] else None,
                    abstract=row["abstract"],
                    indexed_at=datetime.fromisoformat(row["indexed_at"])
                    if row["indexed_at"]
                    else None,
                )
    return None


async def upsert_paper(paper: Paper, db_path: Path | None = None) -> None:
    """Insert or update a paper."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO papers (id, title, authors, abstract, indexed_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                authors = excluded.authors,
                abstract = excluded.abstract,
                indexed_at = excluded.indexed_at
            """,
            (
                paper.id,
                paper.title,
                json.dumps(paper.authors) if paper.authors else None,
                paper.abstract,
                paper.indexed_at.isoformat() if paper.indexed_at else None,
            ),
        )
        await db.commit()


# Chat operations
async def create_chat(
    slug: str, paper_id: str, db_path: Path | None = None
) -> Chat:
    """Create a new chat."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO chats (slug, paper_id) VALUES (?, ?)",
            (slug, paper_id),
        )
        await db.commit()
        chat_id = cursor.lastrowid
        return Chat(
            id=chat_id,
            slug=slug,
            paper_id=paper_id,
            created_at=datetime.now(),
        )


async def get_chat_by_slug(slug: str, db_path: Path | None = None) -> Chat | None:
    """Get a chat by its slug."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chats WHERE slug = ?", (slug,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Chat(
                    id=row["id"],
                    slug=row["slug"],
                    paper_id=row["paper_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
    return None


async def get_chat_by_id(chat_id: int, db_path: Path | None = None) -> Chat | None:
    """Get a chat by its ID."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM chats WHERE id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Chat(
                    id=row["id"],
                    slug=row["slug"],
                    paper_id=row["paper_id"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
    return None


# Message operations
async def add_message(
    chat_id: int, role: str, content: str, db_path: Path | None = None
) -> Message:
    """Add a message to a chat."""
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content),
        )
        await db.commit()
        return Message(
            id=cursor.lastrowid,
            chat_id=chat_id,
            role=role,
            content=content,
            created_at=datetime.now(),
        )


async def get_messages(chat_id: int, db_path: Path | None = None) -> list[Message]:
    """Get all messages for a chat."""
    messages = []
    async with aiosqlite.connect(db_path or DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at",
            (chat_id,),
        ) as cursor:
            async for row in cursor:
                messages.append(
                    Message(
                        id=row["id"],
                        chat_id=row["chat_id"],
                        role=row["role"],
                        content=row["content"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                    )
                )
    return messages
