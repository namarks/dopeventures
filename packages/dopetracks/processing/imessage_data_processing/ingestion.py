"""
Incremental ingestion for prepared iMessage store.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3
import time

from .prepared_messages import (
    ensure_prepared_db,
    parse_message_row,
    bulk_insert_messages,
    bulk_upsert_contacts,
    get_last_processed_rowid,
    set_last_processed_rowid,
    get_last_contact_rowid,
    set_last_contact_rowid,
    set_last_full_reindex,
)


def ingest_messages(source_db_path: str, prepared_db_path: Path, batch_size: int = 1000) -> int:
    """
    Incrementally ingest messages using the last processed ROWID checkpoint.
    """
    last_rowid = get_last_processed_rowid(prepared_db_path)
    processed = 0
    max_rowid_seen = last_rowid

    conn = sqlite3.connect(source_db_path)
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
                    datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc,
                    message.associated_message_type,
                    message.associated_message_guid,
                    message.guid
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


def ingest_contacts(source_db_path: str, prepared_db_path: Path, batch_size: int = 500) -> int:
    """
    Incrementally upsert contacts (handles) by stable handle ROWID.
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


def ingest_prepared_store(
    source_db_path: str,
    base_dir: Optional[Path] = None,
    batch_size: int = 1000,
    contact_batch_size: int = 500,
    force_rebuild: bool = False,
) -> Dict[str, Any]:
    """
    Entry point to build or incrementally update the prepared store.
    """
    prepared_db_path = ensure_prepared_db(base_dir=base_dir, force_rebuild=force_rebuild)

    if force_rebuild:
        set_last_processed_rowid(prepared_db_path, 0)
        set_last_contact_rowid(prepared_db_path, 0)
        set_last_full_reindex(prepared_db_path, int(time.time()))

    msg_count = ingest_messages(source_db_path, prepared_db_path, batch_size=batch_size)
    contact_count = ingest_contacts(source_db_path, prepared_db_path, batch_size=contact_batch_size)

    return {
        "prepared_db_path": str(prepared_db_path),
        "messages_processed": msg_count,
        "contacts_processed": contact_count,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Incrementally ingest Messages DB into prepared store.")
    parser.add_argument("--source-db", required=True, help="Path to chat.db (source Messages database)")
    parser.add_argument("--base-dir", required=False, help="Base directory for prepared DB")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for messages")
    parser.add_argument("--contact-batch-size", type=int, default=500, help="Batch size for contacts")
    parser.add_argument("--force-rebuild", action="store_true", help="Drop and rebuild prepared DB before ingesting")

    args = parser.parse_args()

    result = ingest_prepared_store(
        source_db_path=args.source_db,
        base_dir=Path(args.base_dir) if args.base_dir else None,
        batch_size=args.batch_size,
        contact_batch_size=args.contact_batch_size,
        force_rebuild=args.force_rebuild,
    )
    print(f"Ingestion complete: {result}")

