"""
Tests for dopetracks.processing.imessage_data_processing.fts_indexer.

Covers:
- FTS database creation and schema
- FTS search with parameterized queries (injection prevention)
- FTS status reporting
- FTS availability checks
"""
import os
import sqlite3
import time
from unittest.mock import patch

import pytest

from dopetracks.processing.imessage_data_processing.fts_indexer import (
    get_fts_db_path,
    create_fts_database,
    get_indexed_message_ids,
    search_fts,
    get_fts_status,
    is_fts_available,
)


# ---------------------------------------------------------------------------
# get_fts_db_path
# ---------------------------------------------------------------------------


class TestGetFtsDbPath:
    """Tests for get_fts_db_path()."""

    def test_returns_fts_suffix(self):
        result = get_fts_db_path("/some/path/chat.db")
        assert result == "/some/path/chat.fts.db"

    def test_preserves_directory(self):
        result = get_fts_db_path("/Users/test/Library/Messages/chat.db")
        assert result.startswith("/Users/test/Library/Messages/")
        assert result.endswith(".fts.db")

    def test_different_stem(self):
        result = get_fts_db_path("/data/messages.db")
        assert result == "/data/messages.fts.db"


# ---------------------------------------------------------------------------
# create_fts_database
# ---------------------------------------------------------------------------


class TestCreateFtsDatabase:
    """Tests for create_fts_database()."""

    def test_creates_database_file(self, tmp_path):
        fts_path = str(tmp_path / "test.fts.db")
        assert not os.path.exists(fts_path)
        result = create_fts_database(fts_path)
        assert result is True
        assert os.path.exists(fts_path)

    def test_creates_fts_virtual_table(self, tmp_path):
        fts_path = str(tmp_path / "test.fts.db")
        create_fts_database(fts_path)
        conn = sqlite3.connect(fts_path)
        cur = conn.cursor()
        # FTS5 tables appear in sqlite_master as type 'table'
        cur.execute(
            "SELECT name FROM sqlite_master WHERE name='message_text_fts'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_creates_metadata_table(self, tmp_path):
        fts_path = str(tmp_path / "test.fts.db")
        create_fts_database(fts_path)
        conn = sqlite3.connect(fts_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='message_metadata'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_creates_index_status_table(self, tmp_path):
        fts_path = str(tmp_path / "test.fts.db")
        create_fts_database(fts_path)
        conn = sqlite3.connect(fts_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='fts_index_status'"
        )
        assert cur.fetchone() is not None
        conn.close()

    def test_idempotent_creation(self, tmp_path):
        """Creating the same DB twice should not fail (IF NOT EXISTS)."""
        fts_path = str(tmp_path / "test.fts.db")
        assert create_fts_database(fts_path) is True
        assert create_fts_database(fts_path) is True


# ---------------------------------------------------------------------------
# get_indexed_message_ids
# ---------------------------------------------------------------------------


class TestGetIndexedMessageIds:
    """Tests for get_indexed_message_ids()."""

    def test_empty_db_returns_empty_set(self, fts_db):
        result = get_indexed_message_ids(fts_db)
        assert result == set()

    def test_returns_indexed_ids(self, fts_db):
        conn = sqlite3.connect(fts_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO message_metadata(message_id, chat_id, date, is_from_me, handle_id, has_attributed_body, last_updated) VALUES (100, 1, 0, 0, 1, 0, 0)"
        )
        cur.execute(
            "INSERT INTO message_metadata(message_id, chat_id, date, is_from_me, handle_id, has_attributed_body, last_updated) VALUES (200, 1, 0, 0, 1, 0, 0)"
        )
        conn.commit()
        conn.close()

        result = get_indexed_message_ids(fts_db)
        assert result == {100, 200}

    def test_nonexistent_db_returns_empty_set(self):
        result = get_indexed_message_ids("/nonexistent/path.db")
        assert result == set()


# ---------------------------------------------------------------------------
# search_fts — parameterized queries and injection prevention
# ---------------------------------------------------------------------------


class TestSearchFts:
    """Tests for search_fts() including SQL injection prevention."""

    def _populate_fts(self, fts_db, records):
        """Insert test records into the FTS database.

        Each record is a dict with: message_id, chat_id, date, extracted_text, original_text.
        """
        conn = sqlite3.connect(fts_db)
        cur = conn.cursor()
        for r in records:
            # Insert into metadata table
            cur.execute(
                """INSERT INTO message_metadata
                   (message_id, chat_id, date, is_from_me, handle_id, has_attributed_body, last_updated)
                   VALUES (?, ?, ?, 0, 1, 0, 0)""",
                (r["message_id"], r.get("chat_id", 1), r.get("date", 0)),
            )
            rowid = cur.lastrowid
            # Insert into FTS table with matching rowid
            cur.execute(
                """INSERT INTO message_text_fts(rowid, message_id, chat_id, date, extracted_text, original_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    rowid,
                    r["message_id"],
                    r.get("chat_id", 1),
                    r.get("date", 0),
                    r["extracted_text"],
                    r.get("original_text", r["extracted_text"]),
                ),
            )
        conn.commit()
        conn.close()

    def test_basic_search_returns_results(self, fts_db):
        self._populate_fts(
            fts_db,
            [
                {"message_id": 1, "extracted_text": "hello world spotify"},
                {"message_id": 2, "extracted_text": "goodbye moon"},
            ],
        )
        result = search_fts(fts_db, "hello")
        assert len(result) >= 1
        assert 1 in result["message_id"].values

    def test_search_no_results(self, fts_db):
        self._populate_fts(
            fts_db,
            [{"message_id": 1, "extracted_text": "hello world"}],
        )
        result = search_fts(fts_db, "nonexistentterm")
        assert len(result) == 0

    def test_sql_injection_via_search_term(self, fts_db):
        """Injecting SQL operators into the search term should not crash or cause injection."""
        self._populate_fts(
            fts_db,
            [{"message_id": 1, "extracted_text": "safe message content"}],
        )
        # These payloads should not cause SQL errors or unintended behavior
        injection_payloads = [
            "'; DROP TABLE message_metadata;--",
            '" OR 1=1 --',
            "* NEAR *",
            'hello" OR "1"="1',
            "UNION SELECT * FROM sqlite_master",
        ]
        for payload in injection_payloads:
            # Should not raise, should return a DataFrame (possibly empty)
            result = search_fts(fts_db, payload)
            assert hasattr(result, "columns"), f"Failed for payload: {payload}"

    def test_double_quote_in_search_term(self, fts_db):
        """Double quotes in search terms should be escaped properly."""
        self._populate_fts(
            fts_db,
            [{"message_id": 1, "extracted_text": 'said "hello" to them'}],
        )
        # Searching for the literal word should not crash
        result = search_fts(fts_db, '"hello"')
        assert hasattr(result, "columns")

    def test_search_with_chat_id_filter(self, fts_db):
        self._populate_fts(
            fts_db,
            [
                {"message_id": 1, "chat_id": 10, "extracted_text": "hello from chat 10"},
                {"message_id": 2, "chat_id": 20, "extracted_text": "hello from chat 20"},
            ],
        )
        result = search_fts(fts_db, "hello", chat_ids=[10])
        assert len(result) >= 1
        assert all(cid == 10 for cid in result["chat_id"].values)

    def test_search_with_limit(self, fts_db):
        records = [
            {"message_id": i, "extracted_text": f"message number {i}"}
            for i in range(1, 20)
        ]
        self._populate_fts(fts_db, records)
        result = search_fts(fts_db, "message", limit=5)
        assert len(result) <= 5

    def test_nonexistent_db_returns_empty_dataframe(self):
        result = search_fts("/nonexistent/path.fts.db", "test")
        assert len(result) == 0


# ---------------------------------------------------------------------------
# get_fts_status
# ---------------------------------------------------------------------------


class TestGetFtsStatus:
    """Tests for get_fts_status()."""

    def test_nonexistent_db_returns_none(self):
        result = get_fts_status("/nonexistent/path.fts.db")
        assert result is None

    def test_empty_db_returns_status(self, fts_db):
        result = get_fts_status(fts_db)
        assert result is not None
        assert "total_messages_indexed" in result
        assert result["total_messages_indexed"] == 0

    def test_status_with_data(self, fts_db):
        conn = sqlite3.connect(fts_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO message_metadata(message_id, chat_id, date, is_from_me, handle_id, has_attributed_body, last_updated) VALUES (1, 1, 0, 0, 1, 0, 0)"
        )
        cur.execute(
            """INSERT INTO fts_index_status(source_db_path, last_indexed_date, total_messages_indexed, last_updated)
               VALUES (?, ?, ?, ?)""",
            ("/some/path.db", int(time.time()), 1, int(time.time())),
        )
        conn.commit()
        conn.close()

        result = get_fts_status(fts_db)
        assert result is not None
        assert result["source_db_path"] == "/some/path.db"
        assert result["total_messages_indexed"] >= 1


# ---------------------------------------------------------------------------
# is_fts_available
# ---------------------------------------------------------------------------


class TestIsFtsAvailable:
    """Tests for is_fts_available()."""

    def test_nonexistent_db_returns_false(self):
        assert is_fts_available("/nonexistent/path.fts.db") is False

    def test_empty_db_returns_false(self, fts_db):
        """An FTS DB with no indexed messages should report not available."""
        assert is_fts_available(fts_db) is False

    def test_db_with_data_returns_true(self, fts_db):
        conn = sqlite3.connect(fts_db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO message_metadata(message_id, chat_id, date, is_from_me, handle_id, has_attributed_body, last_updated) VALUES (1, 1, 0, 0, 1, 0, 0)"
        )
        conn.commit()
        conn.close()
        assert is_fts_available(fts_db) is True
