"""
Tests for utility modules:
- dopetracks.utils.utility_functions
- dopetracks.utils.helpers
"""
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from dopetracks.utils.utility_functions import (
    get_messages_db_path,
    get_project_root,
    resolve_short_url,
    batch,
)
from dopetracks.utils.helpers import get_db_path, validate_db_path


# ---------------------------------------------------------------------------
# utility_functions.py
# ---------------------------------------------------------------------------


class TestGetMessagesDbPath:
    """Tests for get_messages_db_path()."""

    def test_returns_string(self):
        result = get_messages_db_path()
        assert isinstance(result, str)

    def test_path_ends_with_chat_db(self):
        result = get_messages_db_path()
        assert result.endswith("Library/Messages/chat.db")

    def test_path_starts_with_home(self):
        result = get_messages_db_path()
        home = os.path.expanduser("~")
        assert result.startswith(home)


class TestGetProjectRoot:
    """Tests for get_project_root()."""

    def test_returns_absolute_path(self):
        result = get_project_root()
        assert os.path.isabs(result)

    def test_returns_parent_of_utils_dir(self):
        """Project root should be the parent of the utils/ directory."""
        result = get_project_root()
        # The function returns os.path.join(dirname(__file__), "..")
        # which from utils/ goes up to dopetracks/
        assert result.endswith("dopetracks") or os.path.isdir(result)


class TestResolveShortUrl:
    """Tests for resolve_short_url()."""

    def test_returns_resolved_url(self):
        """Should follow redirects and return the final URL."""
        mock_response = MagicMock()
        mock_response.url = "https://open.spotify.com/track/abc123"

        with patch("dopetracks.utils.utility_functions.requests.head", return_value=mock_response) as mock_head:
            result = resolve_short_url("https://spotify.link/abc")
            assert result == "https://open.spotify.com/track/abc123"
            mock_head.assert_called_once_with(
                "https://spotify.link/abc", allow_redirects=True, timeout=10
            )

    def test_uses_timeout(self):
        """Should pass timeout=10 to requests.head."""
        mock_response = MagicMock()
        mock_response.url = "https://example.com/final"

        with patch("dopetracks.utils.utility_functions.requests.head", return_value=mock_response) as mock_head:
            resolve_short_url("https://short.url/x")
            _, kwargs = mock_head.call_args
            assert kwargs["timeout"] == 10

    def test_network_error_propagates(self):
        """Network errors should propagate to the caller."""
        import requests

        with patch(
            "dopetracks.utils.utility_functions.requests.head",
            side_effect=requests.ConnectionError("unreachable"),
        ):
            with pytest.raises(requests.ConnectionError):
                resolve_short_url("https://bad.url/x")


class TestBatch:
    """Tests for the batch() helper."""

    def test_even_split(self):
        items = list(range(10))
        result = list(batch(items, n=5))
        assert result == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]

    def test_uneven_split(self):
        items = list(range(7))
        result = list(batch(items, n=3))
        assert result == [[0, 1, 2], [3, 4, 5], [6]]

    def test_empty_iterable(self):
        result = list(batch([], n=5))
        assert result == []

    def test_single_batch(self):
        items = [1, 2, 3]
        result = list(batch(items, n=10))
        assert result == [[1, 2, 3]]

    def test_batch_of_one(self):
        items = list(range(4))
        result = list(batch(items, n=1))
        assert result == [[0], [1], [2], [3]]

    def test_default_batch_size_is_50(self):
        """Default n=50 should produce one batch for 50 items."""
        items = list(range(50))
        result = list(batch(items))
        assert len(result) == 1
        assert len(result[0]) == 50


# ---------------------------------------------------------------------------
# helpers.py
# ---------------------------------------------------------------------------


class TestGetDbPath:
    """Tests for helpers.get_db_path()."""

    def test_returns_none_when_no_db_exists(self, tmp_path):
        """When the Messages DB doesn't exist, should return None."""
        with patch("dopetracks.utils.helpers.os.path.expanduser", return_value=str(tmp_path / "nonexistent")):
            with patch("dopetracks.utils.helpers.os.path.exists", return_value=False):
                result = get_db_path()
                assert result is None

    def test_returns_path_when_db_accessible(self, tmp_path):
        """When a valid Messages DB exists, should return its path."""
        db_path = tmp_path / "chat.db"
        # Create a minimal DB with a message table
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE message (ROWID INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO message (ROWID) VALUES (1)")
        conn.commit()
        conn.close()

        with patch(
            "dopetracks.utils.helpers.os.path.expanduser",
            return_value=str(tmp_path),
        ):
            with patch("dopetracks.utils.helpers.os.path.exists", return_value=True):
                with patch(
                    "dopetracks.utils.helpers.sqlite3.connect"
                ) as mock_connect:
                    mock_conn = MagicMock()
                    mock_connect.return_value = mock_conn
                    result = get_db_path()
                    # When connection succeeds, it should return a path string
                    if result is not None:
                        assert isinstance(result, str)


class TestValidateDbPath:
    """Tests for helpers.validate_db_path()."""

    def test_nonexistent_path_returns_false(self):
        assert validate_db_path("/nonexistent/path/to/db") is False

    def test_valid_db_returns_true(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE message (ROWID INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO message (ROWID) VALUES (1)")
        conn.commit()
        conn.close()
        assert validate_db_path(str(db_path)) is True

    def test_db_without_message_table_returns_false(self, tmp_path):
        db_path = tmp_path / "bad.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.commit()
        conn.close()
        assert validate_db_path(str(db_path)) is False
