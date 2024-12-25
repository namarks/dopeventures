import sqlite3
import os
import json

def initialize_cache(db_path=None):
    """
    Initialize the SQLite database for caching.

    Args:
        db_path (str): Path to the database file. Defaults to `~/.spotify_cache/spotify_cache.db`.

    Returns:
        conn (sqlite3.Connection): SQLite connection object.
        cursor (sqlite3.Cursor): SQLite cursor object.
    """
    if db_path is None:
        cache_dir = os.path.expanduser("~/.spotify_cache")
        os.makedirs(cache_dir, exist_ok=True)  # Create directory if it doesn't exist
        db_path = os.path.join(cache_dir, "spotify_cache.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            url TEXT PRIMARY KEY,
            metadata TEXT
        )
    """)
    conn.commit()
    return conn, cursor

def save_to_cache(cursor, url, metadata):
    """
    Save metadata for a URL to the cache.

    Args:
        cursor (sqlite3.Cursor): SQLite cursor object.
        url (str): Spotify URL.
        metadata (dict): Metadata to store (as a JSON string).
    """
    cursor.execute(
        "INSERT OR REPLACE INTO cache (url, metadata) VALUES (?, ?)",
        (url, json.dumps(metadata))
    )

def load_from_cache(cursor, url):
    """
    Load metadata for a URL from the cache.

    Args:
        cursor (sqlite3.Cursor): SQLite cursor object.
        url (str): Spotify URL.

    Returns:
        dict: Metadata for the URL, or None if not found.
    """
    cursor.execute("SELECT metadata FROM cache WHERE url = ?", (url,))
    row = cursor.fetchone()
    return json.loads(row[0]) if row else None

if __name__ == "__main__":
    initialize_cache()
