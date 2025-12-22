import sqlite3
import sys
from pathlib import Path

import pytest

# Add project packages to sys.path for imports
ROOT_PACKAGES = Path(__file__).resolve().parents[4]
if str(ROOT_PACKAGES) not in sys.path:
    sys.path.append(str(ROOT_PACKAGES))

from dopetracks.processing.imessage_data_processing import ingestion
from dopetracks.processing.imessage_data_processing import prepared_messages as pm


def build_source_db(db_path: Path, messages, handles):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE message (
            ROWID INTEGER PRIMARY KEY,
            text TEXT,
            attributedBody BLOB,
            date INTEGER,
            is_from_me INTEGER,
            handle_id INTEGER
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
        """
    )
    for handle in handles:
        cur.execute(
            "INSERT INTO handle(ROWID, id, uncanonicalized_id) VALUES (?, ?, ?)",
            (handle["rowid"], handle["id"], handle.get("uncanonicalized_id")),
        )
    for msg in messages:
        cur.execute(
            """
            INSERT INTO message(ROWID, text, attributedBody, date, is_from_me, handle_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                msg["rowid"],
                msg["text"],
                msg.get("attributedBody"),
                msg.get("date", 0),
                msg.get("is_from_me", 0),
                msg.get("handle_id"),
            ),
        )
        cur.execute(
            "INSERT INTO chat_message_join(chat_id, message_id) VALUES (?, ?)",
            (msg.get("chat_id", 1), msg["rowid"]),
        )
    conn.commit()
    conn.close()


def test_ingest_messages_and_contacts(tmp_path: Path):
    source_db = tmp_path / "source.db"
    messages = [
        {
            "rowid": 1,
            "chat_id": 10,
            "text": "hello https://open.spotify.com/track/123",
            "date": int(1e9),
            "is_from_me": 0,
            "handle_id": 1,
        }
    ]
    handles = [{"rowid": 1, "id": "+15555555555"}]
    build_source_db(source_db, messages, handles)

    prepared_dir = tmp_path / "prepared"
    result = ingestion.ingest_prepared_store(
        source_db_path=str(source_db),
        base_dir=prepared_dir,
        batch_size=10,
        contact_batch_size=10,
        force_rebuild=True,
    )

    prepared_db_path = Path(result["prepared_db_path"])
    conn = sqlite3.connect(prepared_db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages")
    message_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM contacts")
    contact_count = cur.fetchone()[0]
    cur.execute("SELECT content_hash FROM messages LIMIT 1")
    content_hash = cur.fetchone()[0]
    conn.close()

    assert message_count == 1
    assert contact_count == 1
    assert content_hash is not None and len(content_hash) > 10
    assert pm.get_last_processed_rowid(prepared_db_path) == 1
    assert pm.get_last_contact_rowid(prepared_db_path) == 1


def test_incremental_ingest_only_appends(tmp_path: Path):
    source_db = tmp_path / "source.db"
    messages = [
        {"rowid": 1, "chat_id": 10, "text": "first", "date": int(1e9), "is_from_me": 0, "handle_id": 1},
        {"rowid": 2, "chat_id": 10, "text": "second", "date": int(2e9), "is_from_me": 1, "handle_id": 1},
    ]
    handles = [{"rowid": 1, "id": "+15555555555"}]
    build_source_db(source_db, messages, handles)

    prepared_dir = tmp_path / "prepared"
    ingestion.ingest_prepared_store(
        source_db_path=str(source_db),
        base_dir=prepared_dir,
        batch_size=10,
        contact_batch_size=10,
        force_rebuild=True,
    )

    # Append a new message to source DB
    conn = sqlite3.connect(source_db)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO message(ROWID, text, attributedBody, date, is_from_me, handle_id) VALUES (?, ?, ?, ?, ?, ?)",
        (3, "third", None, int(3e9), 0, 1),
    )
    cur.execute("INSERT INTO chat_message_join(chat_id, message_id) VALUES (?, ?)", (10, 3))
    conn.commit()
    conn.close()

    result = ingestion.ingest_prepared_store(
        source_db_path=str(source_db),
        base_dir=prepared_dir,
        batch_size=10,
        contact_batch_size=10,
        force_rebuild=False,
    )
    prepared_db_path = Path(result["prepared_db_path"])

    conn = sqlite3.connect(prepared_db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM messages")
    message_count = cur.fetchone()[0]
    conn.close()

    assert message_count == 3
    assert result["messages_processed"] == 1
    assert pm.get_last_processed_rowid(prepared_db_path) == 3


def test_force_rebuild_resets_checkpoints(tmp_path: Path):
    source_db = tmp_path / "source.db"
    messages = [
        {"rowid": 1, "chat_id": 10, "text": "first", "date": int(1e9), "is_from_me": 0, "handle_id": 1},
    ]
    handles = [{"rowid": 1, "id": "+15555555555"}]
    build_source_db(source_db, messages, handles)

    prepared_dir = tmp_path / "prepared"
    ingestion.ingest_prepared_store(
        source_db_path=str(source_db),
        base_dir=prepared_dir,
        batch_size=10,
        contact_batch_size=10,
        force_rebuild=True,
    )

    # Re-run with force_rebuild to ensure checkpoints reset and schema version persists
    result = ingestion.ingest_prepared_store(
        source_db_path=str(source_db),
        base_dir=prepared_dir,
        batch_size=10,
        contact_batch_size=10,
        force_rebuild=True,
    )
    prepared_db_path = Path(result["prepared_db_path"])

    conn = sqlite3.connect(prepared_db_path)
    cur = conn.cursor()
    cur.execute("SELECT value FROM meta WHERE key='db_version'")
    db_version = cur.fetchone()[0]
    conn.close()

    assert db_version == str(pm.PREPARED_DB_VERSION)
    assert pm.get_last_processed_rowid(prepared_db_path) == 1
    assert pm.get_last_contact_rowid(prepared_db_path) == 1

