"""
Helper functions for Dopetracks application.
"""
import os
import sqlite3
from typing import Optional
from pathlib import Path

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
                return path
            except Exception:
                continue
    
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

