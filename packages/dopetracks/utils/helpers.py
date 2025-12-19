"""
Helper functions for Dopetracks application.
"""
import os
import sqlite3
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

def get_db_path() -> Optional[str]:
    """
    Get the Messages database path.
    Tries multiple common locations.
    """
    # Try system paths
    system_user = os.path.expanduser("~").split("/")[-1]
    possible_paths = [
        f"/Users/{system_user}/Library/Messages/chat.db",
        os.path.expanduser("~/Library/Messages/chat.db")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                # Test database access
                conn = sqlite3.connect(path)
                conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
                conn.close()
                logger.info(f"Successfully accessed Messages database at {path}")
                return path
            except PermissionError as e:
                logger.warning(f"Permission denied accessing {path}: {e}")
                logger.warning("Full Disk Access may be required. Go to System Preferences > Security & Privacy > Privacy > Full Disk Access")
                continue
            except sqlite3.Error as e:
                logger.warning(f"SQLite error accessing {path}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Unexpected error accessing {path}: {e}")
                continue
        else:
            logger.debug(f"Messages database not found at {path}")
    
    logger.error("Could not find or access Messages database. Please grant Full Disk Access or specify database path manually.")
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

