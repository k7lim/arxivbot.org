"""Tests for the /health endpoint."""

import sqlite3

from arxivbot import config


def _point_db_at(monkeypatch, path):
    monkeypatch.setattr(
        config, "_settings", config.Settings(_env_file=None, database_path=path)
    )


def test_health_ok_when_db_initialized(client):
    db_path = str(config.get_settings().database_path)

    r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "connected"}
    assert "path" not in r.json()
    assert db_path not in r.text


def test_health_503_when_db_missing_and_does_not_create_it(
    client, tmp_path, monkeypatch
):
    missing = tmp_path / "missing" / "nope.db"
    _point_db_at(monkeypatch, missing)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json() == {"status": "error", "database": "unavailable"}
    assert str(missing) not in r.text
    assert not missing.exists()
    assert not missing.parent.exists()


def test_health_503_when_schema_missing(client, tmp_path, monkeypatch):
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    _point_db_at(monkeypatch, empty)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json() == {"status": "error", "database": "unavailable"}
    assert "chats" not in r.text
