"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from arxivbot import config
from arxivbot.limiter import limiter


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient against the real app with a temp DB and no .env or API keys."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(
        config,
        "_settings",
        config.Settings(_env_file=None, database_path=tmp_path / "test.db"),
    )
    limiter.reset()

    from arxivbot.main import app

    with TestClient(app) as c:
        yield c
    limiter.reset()
