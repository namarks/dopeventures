"""
Helper functions for Dopetracks application.
"""
import os
import sqlite3
import logging
from typing import Optional
from pathlib import Path

from ..processing.imessage_data_processing.imessage_db import get_user_db_path

logger = logging.getLogger(__name__)

def get_db_path() -> Optional[str]:
    """
    Get the Messages database path.
    Delegates to the canonical implementation in imessage_db and adds
    user-facing logging (e.g. Full Disk Access hint on failure).
    """
    result = get_user_db_path()
    if result:
        logger.info(f"Successfully accessed Messages database at {result}")
        return result

    logger.error(
        "Could not find or access Messages database. "
        "Full Disk Access may be required. "
        "Go to System Preferences > Security & Privacy > Privacy > Full Disk Access"
    )
    return None

def validate_db_path(db_path: str) -> bool:
    """Validate that a database path is accessible and valid."""
    if not os.path.exists(db_path):
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
        conn.close()
        return True
    except Exception:
        return False

