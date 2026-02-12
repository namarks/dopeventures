"""
Shared test fixtures for Dopetracks test suite.

Provides:
- In-memory SQLite databases for testing
- Mock settings that don't depend on a real .env file
- FastAPI test client with mocked dependencies
"""
import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the packages root is on sys.path so dopetracks is importable
_PACKAGES_ROOT = Path(__file__).resolve().parents[2]  # packages/
if str(_PACKAGES_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGES_ROOT))


# ---------------------------------------------------------------------------
# Environment: set safe defaults BEFORE any dopetracks module is imported
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    """Ensure every test gets a clean, predictable environment.

    Sets ALLOW_MISSING_SETTINGS so that config.py does not warn/fail on
    import when Spotify credentials are absent.
    """
    monkeypatch.setenv("ALLOW_MISSING_SETTINGS", "true")


# ---------------------------------------------------------------------------
# In-memory iMessage-style source database
# ---------------------------------------------------------------------------
@pytest.fixture
def source_db(tmp_path):
    """Create a minimal iMessage-style SQLite database and return its path."""
    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            text TEXT,
            attributedBody BLOB,
            date INTEGER,
            is_from_me INTEGER,
            handle_id INTEGER,
            associated_message_type INTEGER
        );
        CREATE TABLE chat (
            ROWID INTEGER PRIMARY KEY,
            display_name TEXT,
            chat_identifier TEXT
        );
        CREATE TABLE chat_message_join (
            chat_id INTEGER,
            message_id INTEGER
        );
        CREATE TABLE handle (
            ROWID INTEGER PRIMARY KEY,
            id TEXT,
            uncanonicalized_id TEXT
        );
        CREATE TABLE chat_handle_join (
            chat_id INTEGER,
            handle_id INTEGER
        );
        """
    )
    conn.commit()
    conn.close()
    return str(db_path)


def populate_source_db(db_path, messages, handles, chats=None):
    """Helper to populate a source database with test data."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if chats:
        for chat in chats:
            cur.execute(
                "INSERT INTO chat(ROWID, display_name, chat_identifier) VALUES (?, ?, ?)",
                (chat["rowid"], chat.get("display_name", ""), chat.get("chat_identifier", "")),
            )
    for handle in handles:
        cur.execute(
            "INSERT INTO handle(ROWID, id, uncanonicalized_id) VALUES (?, ?, ?)",
            (handle["rowid"], handle["id"], handle.get("uncanonicalized_id")),
        )
    for msg in messages:
        cur.execute(
            """INSERT INTO message(ROWID, text, attributedBody, date, is_from_me, handle_id, associated_message_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                msg["rowid"],
                msg.get("text"),
                msg.get("attributedBody"),
                msg.get("date", 0),
                msg.get("is_from_me", 0),
                msg.get("handle_id"),
                msg.get("associated_message_type"),
            ),
        )
        cur.execute(
            "INSERT INTO chat_message_join(chat_id, message_id) VALUES (?, ?)",
            (msg.get("chat_id", 1), msg["rowid"]),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# FTS database fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def fts_db(tmp_path):
    """Create a fresh FTS database and return its path."""
    from dopetracks.processing.imessage_data_processing.fts_indexer import create_fts_database

    fts_path = str(tmp_path / "test.fts.db")
    create_fts_database(fts_path)
    return fts_path
