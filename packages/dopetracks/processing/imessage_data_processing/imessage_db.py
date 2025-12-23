import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

# Apple timestamp epoch (January 1, 2001, UTC)
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def convert_to_apple_timestamp(date_str: str) -> int:
    """Convert ISO date string to Apple timestamp (nanoseconds since 2001-01-01 UTC)."""
    # Normalize to timezone-aware UTC to avoid naive/aware subtraction errors
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    delta = dt - APPLE_EPOCH
    return int(delta.total_seconds() * 1e9)


@contextmanager
def db_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    """Context-managed sqlite connection to ensure proper cleanup."""
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception as exc:  # pragma: no cover - best effort close
            logger.warning(f"Failed to close connection for {db_path}: {exc}")


def get_user_db_path() -> Optional[str]:
    """
    Get the Messages database path for the current user.

    Returns the standard macOS Messages database path.
    For single-user setup, this is always ~/Library/Messages/chat.db
    """
    default_path = os.path.expanduser("~/Library/Messages/chat.db")

    if os.path.exists(default_path):
        try:
            with db_connection(default_path) as conn:
                conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
            return default_path
        except Exception as exc:
            logger.warning(f"Messages database exists but cannot be accessed: {exc}")
            return None

    return None

