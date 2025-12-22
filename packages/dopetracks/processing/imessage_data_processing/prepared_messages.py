import os
import sqlite3
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Iterable

from . import parsing_utils as pu

PREPARED_DB_NAME = "prepared_messages.db"
PREPARED_DB_VERSION = 2

# Meta keys tracked inside the prepared store
META_KEYS = {
    "db_version": str(PREPARED_DB_VERSION),
    "last_processed_rowid": "0",
    "last_contact_rowid": "0",
    "last_full_reindex": "0",
}


def _set_meta(cur: sqlite3.Cursor, key: str, value: str) -> None:
    cur.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def _get_meta(cur: sqlite3.Cursor, key: str, default: Optional[str] = None) -> Optional[str]:
    cur.execute("SELECT value FROM meta WHERE key = ?", (key,))
    row = cur.fetchone()
    if row and row[0] is not None:
        return row[0]
    return default


def _drop_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("DROP TABLE IF EXISTS messages")
    cur.execute("DROP TABLE IF EXISTS contacts")
    cur.execute("DROP TABLE IF EXISTS meta")
    cur.execute("DROP TABLE IF EXISTS messages_fts")


def _create_schema(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY,
            chat_id INTEGER,
            date TEXT,
            sender_handle TEXT,
            is_from_me INTEGER,
            text TEXT,
            has_spotify_link INTEGER DEFAULT 0,
            spotify_url TEXT,
            content_hash TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS contacts (
            handle_id INTEGER PRIMARY KEY,
            contact_info TEXT,
            display_name TEXT,
            avatar_path TEXT,
            stable_id TEXT,
            last_seen TEXT
        )
        """
    )
    # FTS for text search
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
        USING fts5(text, content='messages', content_rowid='message_id')
        """
    )
    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_content_hash ON messages(content_hash)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_contacts_stable_id ON contacts(stable_id)")
    # Seed meta with defaults
    for key, value in META_KEYS.items():
        cur.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES(?, ?)",
            (key, value),
        )


def _ensure_schema(conn: sqlite3.Connection, force_rebuild: bool = False) -> None:
    cur = conn.cursor()
    needs_rebuild = force_rebuild

    # Detect version drift
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='meta'")
        has_meta = cur.fetchone() is not None
        current_version = None
        if has_meta:
            current_version = _get_meta(cur, "db_version")
            if current_version != str(PREPARED_DB_VERSION):
                needs_rebuild = True
        else:
            needs_rebuild = True
    except Exception:
        needs_rebuild = True

    if needs_rebuild:
        _drop_schema(cur)

    _create_schema(cur)
    _set_meta(cur, "db_version", str(PREPARED_DB_VERSION))
    conn.commit()


def get_prepared_db_path(base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        base_dir = Path.home() / "Library" / "Application Support" / "Dopetracks"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / PREPARED_DB_NAME


def ensure_prepared_db(base_dir: Optional[Path] = None, force_rebuild: bool = False) -> Path:
    """
    Ensure the prepared DB exists, is on the expected schema version, and is ready for use.
    A force_rebuild will drop and recreate schema (used on manual reindex or version mismatch).
    """
    db_path = get_prepared_db_path(base_dir)
    conn = sqlite3.connect(db_path)
    try:
        _ensure_schema(conn, force_rebuild=force_rebuild)
        if force_rebuild:
            _set_meta(conn.cursor(), "last_full_reindex", str(int(time.time())))
            conn.commit()
    finally:
        conn.close()
    return db_path


def ensure_prepared_populated(
    source_db_path: str,
    base_dir: Optional[Path] = None,
    force_rebuild: bool = False,
) -> Path:
    """
    Ensure prepared DB exists and is populated with at least the latest messages.
    Returns path to prepared DB.
    """
    db_path = ensure_prepared_db(base_dir, force_rebuild=force_rebuild)
    if not source_db_path or not os.path.exists(source_db_path):
        return db_path
    # If we have nothing processed yet, do an initial load
    last_rowid = get_last_processed_rowid(db_path)
    if last_rowid == 0:
        load_new_messages_into_prepared_db(source_db_path, db_path)
    else:
        # Incremental update
        load_new_messages_into_prepared_db(source_db_path, db_path)

    # Always update contacts incrementally
    load_new_contacts_into_prepared_db(source_db_path, db_path)
    return db_path


def _get_int_meta(db_path: Path, key: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        value = _get_meta(cur, key, "0")
        return int(value) if value is not None else 0
    finally:
        conn.close()


def _set_int_meta(db_path: Path, key: str, value: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        _set_meta(cur, key, str(value))
        conn.commit()
    finally:
        conn.close()


def get_last_processed_rowid(db_path: Path) -> int:
    return _get_int_meta(db_path, "last_processed_rowid")


def set_last_processed_rowid(db_path: Path, rowid: int) -> None:
    _set_int_meta(db_path, "last_processed_rowid", rowid)


def get_last_contact_rowid(db_path: Path) -> int:
    return _get_int_meta(db_path, "last_contact_rowid")


def set_last_contact_rowid(db_path: Path, rowid: int) -> None:
    _set_int_meta(db_path, "last_contact_rowid", rowid)


def set_last_full_reindex(db_path: Path, timestamp: int) -> None:
    _set_int_meta(db_path, "last_full_reindex", timestamp)


def get_last_full_reindex(db_path: Path) -> int:
    return _get_int_meta(db_path, "last_full_reindex")


def filter_chat_ids_by_message_content(
    prepared_db_path: Path,
    search_term: str,
    chat_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10000,
) -> List[int]:
    """
    Use prepared DB FTS to find chat_ids containing the search term.
    """
    conn = sqlite3.connect(prepared_db_path)
    try:
        cur = conn.cursor()
        where_clauses = ["messages_fts MATCH ?"]
        params: List[Any] = [search_term]

        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            where_clauses.append(f"messages.chat_id IN ({placeholders})")
            params.extend(chat_ids)
        if start_date:
            where_clauses.append("messages.date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("messages.date <= ?")
            params.append(end_date)

        query = f"""
            SELECT DISTINCT messages.chat_id
            FROM messages_fts
            JOIN messages ON messages_fts.rowid = messages.message_id
            WHERE {' AND '.join(where_clauses)}
            ORDER BY messages.date DESC
            LIMIT ?
        """
        params.append(limit)
        cur.execute(query, params)
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def get_recent_messages_prepared(
    prepared_db_path: Path,
    chat_id: int,
    limit: int = 5,
    offset: int = 0,
    order: str = "desc",
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch recent messages for a chat from the prepared store, optionally filtered by search.
    """
    conn = sqlite3.connect(prepared_db_path)
    try:
        cur = conn.cursor()
        order_sql = "DESC" if order.lower() != "asc" else "ASC"
        params: List[Any] = [chat_id]

        if search:
            # Use FTS for search within chat
            cur.execute(
                f"""
                SELECT messages.message_id
                FROM messages_fts
                JOIN messages ON messages_fts.rowid = messages.message_id
                WHERE messages.chat_id = ?
                AND messages_fts MATCH ?
                ORDER BY messages.date {order_sql}
                LIMIT ? OFFSET ?
                """,
                (chat_id, search, limit, offset),
            )
            message_ids = [row[0] for row in cur.fetchall()]
            if not message_ids:
                return []
            placeholders = ",".join("?" * len(message_ids))
            params = message_ids + [limit, offset]
            cur.execute(
                f"""
                SELECT message_id, chat_id, date, sender_handle, is_from_me, text, has_spotify_link, spotify_url
                FROM messages
                WHERE message_id IN ({placeholders})
                ORDER BY date {order_sql}
                LIMIT ? OFFSET ?
                """,
                params,
            )
        else:
            cur.execute(
                f"""
                SELECT message_id, chat_id, date, sender_handle, is_from_me, text, has_spotify_link, spotify_url
                FROM messages
                WHERE chat_id = ?
                ORDER BY date {order_sql}
                LIMIT ? OFFSET ?
                """,
                (chat_id, limit, offset),
            )

        rows = cur.fetchall()
        return [
            {
                "message_id": row[0],
                "chat_id": row[1],
                "date": row[2],
                "sender_handle": row[3],
                "is_from_me": bool(row[4]),
                "text": row[5],
                "has_spotify_link": bool(row[6]),
                "spotify_url": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def get_chat_overview(
    prepared_db_path: Path,
    limit_to_recent: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return aggregate stats per chat from the prepared store.
    """
    conn = sqlite3.connect(prepared_db_path)
    try:
        cur = conn.cursor()
        query = """
            SELECT
                chat_id,
                COUNT(*) as message_count,
                SUM(is_from_me) as from_me_count,
                MIN(date) as first_date,
                MAX(date) as last_date
            FROM messages
            GROUP BY chat_id
            ORDER BY last_date DESC
        """
        if limit_to_recent:
            query += f" LIMIT {int(limit_to_recent)}"
        cur.execute(query)
        rows = cur.fetchall()
        return [
            {
                "chat_id": row[0],
                "message_count": row[1],
                "from_me_count": row[2],
                "first_message_date": row[3],
                "last_message_date": row[4],
            }
            for row in rows
        ]
    finally:
        conn.close()


def parse_message_row(row: Tuple[Any, ...]) -> Dict[str, Any]:
    (
        message_id,
        chat_id,
        text,
        attributed_body,
        is_from_me,
        handle_id,
        sender_contact,
        date_utc,
    ) = row
    parsed = pu.parse_message_fields(text, attributed_body, sender_contact, date_utc)
    return {
        "message_id": message_id,
        "chat_id": chat_id,
        "date": date_utc,
        "sender_handle": sender_contact,
        "is_from_me": 1 if is_from_me else 0,
        "text": parsed["final_text"],
        "has_spotify_link": parsed["has_spotify"],
        "spotify_url": parsed["spotify_url"],
        "content_hash": parsed["content_hash"],
    }


def bulk_insert_messages(db_path: Path, messages: List[Dict[str, Any]]) -> None:
    if not messages:
        return
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA synchronous = OFF;")
        cur.execute("PRAGMA journal_mode = WAL;")
        rows = [
            (
                m["message_id"],
                m["chat_id"],
                m["date"],
                m["sender_handle"],
                m["is_from_me"],
                m["text"],
                m["has_spotify_link"],
                m["spotify_url"],
                m.get("content_hash"),
            )
            for m in messages
        ]
        cur.executemany(
            """
            INSERT OR REPLACE INTO messages
            (message_id, chat_id, date, sender_handle, is_from_me, text, has_spotify_link, spotify_url, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        # Update FTS
        cur.executemany(
            "INSERT OR REPLACE INTO messages_fts(rowid, text) VALUES(?, ?)",
            [(m["message_id"], m["text"]) for m in messages],
        )
        conn.commit()
    finally:
        conn.close()


def bulk_upsert_contacts(db_path: Path, contacts: Iterable[Dict[str, Any]]) -> int:
    contacts_list = list(contacts)
    if not contacts_list:
        return 0
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA synchronous = OFF;")
        cur.execute("PRAGMA journal_mode = WAL;")
        rows = [
            (
                c.get("handle_id"),
                c.get("contact_info"),
                c.get("display_name"),
                c.get("avatar_path"),
                c.get("stable_id"),
                c.get("last_seen"),
            )
            for c in contacts_list
        ]
        cur.executemany(
            """
            INSERT INTO contacts(handle_id, contact_info, display_name, avatar_path, stable_id, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(handle_id) DO UPDATE SET
                contact_info=excluded.contact_info,
                display_name=excluded.display_name,
                avatar_path=excluded.avatar_path,
                stable_id=excluded.stable_id,
                last_seen=excluded.last_seen
            """,
            rows,
        )
        conn.commit()
        return len(contacts_list)
    finally:
        conn.close()


def load_new_contacts_into_prepared_db(
    source_db_path: str,
    prepared_db_path: Path,
    batch_size: int = 500,
) -> int:
    """
    Incrementally load contacts from source Messages DB into prepared DB.
    """
    last_contact_rowid = get_last_contact_rowid(prepared_db_path)
    processed = 0
    max_rowid_seen = last_contact_rowid

    conn = sqlite3.connect(source_db_path)
    try:
        cur = conn.cursor()
        while True:
            cur.execute(
                """
                SELECT
                    handle.ROWID as handle_id,
                    handle.id as contact_info,
                    handle.uncanonicalized_id as display_name
                FROM handle
                WHERE handle.ROWID > ?
                ORDER BY handle.ROWID ASC
                LIMIT ?
                """,
                (last_contact_rowid, batch_size),
            )
            rows = cur.fetchall()
            if not rows:
                break

            contacts = []
            for row in rows:
                handle_id, contact_info, display_name = row
                contacts.append(
                    {
                        "handle_id": handle_id,
                        "contact_info": contact_info,
                        "display_name": display_name or contact_info,
                        "avatar_path": None,
                        "stable_id": handle_id,
                        "last_seen": None,
                    }
                )
            bulk_upsert_contacts(prepared_db_path, contacts)
            processed += len(contacts)
            max_rowid_seen = rows[-1][0]
            last_contact_rowid = max_rowid_seen
    finally:
        conn.close()

    if processed > 0:
        set_last_contact_rowid(prepared_db_path, max_rowid_seen)
    return processed


def load_new_messages_into_prepared_db(
    source_db_path: str,
    prepared_db_path: Path,
    batch_size: int = 1000,
) -> int:
    """
    Load new messages from source Messages DB into prepared DB.
    Returns the count of messages processed.
    """
    last_rowid = get_last_processed_rowid(prepared_db_path)
    conn = sqlite3.connect(source_db_path)
    processed = 0
    max_rowid_seen = last_rowid
    try:
        cur = conn.cursor()
        while True:
            cur.execute(
                """
                SELECT
                    message.ROWID as message_id,
                    chat_message_join.chat_id as chat_id,
                    message.text,
                    message.attributedBody,
                    message.is_from_me,
                    message.handle_id,
                    handle.id as sender_contact,
                    datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
                FROM message
                JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
                LEFT JOIN handle ON message.handle_id = handle.ROWID
                WHERE message.ROWID > ?
                ORDER BY message.ROWID ASC
                LIMIT ?
                """,
                (last_rowid, batch_size),
            )
            rows = cur.fetchall()
            if not rows:
                break
            messages = [parse_message_row(row) for row in rows]
            bulk_insert_messages(prepared_db_path, messages)
            processed += len(messages)
            max_rowid_seen = rows[-1][0]
            last_rowid = max_rowid_seen
    finally:
        conn.close()
    if processed > 0:
        set_last_processed_rowid(prepared_db_path, max_rowid_seen)
    return processed


def advanced_search_prepared(
    prepared_db_path: Path,
    query: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    participant_list: Optional[List[str]],
    message_content: Optional[str],
    limit_to_recent: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Search chats by participants/text/date using the prepared DB.
    Currently returns chat-level aggregates similar to advanced_chat_search.
    """
    conn = sqlite3.connect(prepared_db_path)
    try:
        cur = conn.cursor()
        where_clauses = []
        params: List[Any] = []
        
        if participant_list:
            # For prepared DB we do not store participant list directly; skip for now or integrate later.
            pass
        
        if start_date:
            where_clauses.append("date >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("date <= ?")
            params.append(end_date)
        
        message_ids = None
        if message_content:
            cur.execute(
                "SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?",
                (message_content,),
            )
            message_ids = {row[0] for row in cur.fetchall()}
            if not message_ids:
                return []
        
        # Aggregate by chat_id
        query_sql = """
            SELECT
                chat_id,
                COUNT(*) as message_count,
                SUM(is_from_me) as from_me_count,
                MIN(date) as first_date,
                MAX(date) as last_date
            FROM messages
        """
        conditions = []
        if where_clauses:
            conditions.extend(where_clauses)
        if message_ids is not None:
            conditions.append(f"message_id IN ({','.join(['?']*len(message_ids))})")
            params.extend(list(message_ids))
        if conditions:
            query_sql += " WHERE " + " AND ".join(conditions)
        query_sql += " GROUP BY chat_id ORDER BY last_date DESC"
        if limit_to_recent:
            query_sql += f" LIMIT {int(limit_to_recent)}"
        
        cur.execute(query_sql, params)
        rows = cur.fetchall()
        results = []
        for row in rows:
            chat_id, msg_count, from_me_count, first_date, last_date = row
            results.append(
                {
                    "chat_id": chat_id,
                    "message_count": msg_count,
                    "from_me_count": from_me_count,
                    "first_message_date": first_date,
                    "last_message_date": last_date,
                }
            )
        return results
    finally:
        conn.close()


def chat_search_prepared(
    prepared_db_path: Path,
    query: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    participant_list: Optional[List[str]],
    message_content: Optional[str],
    limit_to_recent: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Return chat-level info from prepared DB (chat_id, message_count, first/last date).
    This is similar to advanced search but intended for chat list search. Participant filter is not applied here.
    """
    return advanced_search_prepared(
        prepared_db_path,
        query,
        start_date,
        end_date,
        participant_list,
        message_content,
        limit_to_recent,
    )


