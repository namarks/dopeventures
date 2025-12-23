"""
Incremental ingestion for prepared iMessage store.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import sqlite3
import time
from collections import defaultdict

from .handle_utils import normalize_handle, normalize_handle_variants
from .prepared_messages import (
    ensure_prepared_db,
    parse_message_row,
    bulk_insert_messages,
    bulk_upsert_contacts,
    bulk_upsert_chat_groups,
    get_last_processed_rowid,
    set_last_processed_rowid,
    get_last_processed_date,
    set_last_processed_date,
    get_last_contact_rowid,
    set_last_contact_rowid,
    set_last_full_reindex,
)


def ingest_messages(source_db_path: str, prepared_db_path: Path, batch_size: int = 1000) -> int:
    """
    Incrementally ingest messages using the last processed ROWID checkpoint.
    """
    last_rowid = get_last_processed_rowid(prepared_db_path)
    last_date = get_last_processed_date(prepared_db_path)
    processed = 0
    max_rowid_seen = last_rowid
    max_date_seen: Optional[str] = last_date
    chat_to_canonical, canonical_members = _build_canonical_map(source_db_path)
    canonical_last_date: Dict[str, str] = {}

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

            messages = []
            for row in rows:
                msg = parse_message_row(row)
                chat_id = msg["chat_id"]
                canonical = chat_to_canonical.get(chat_id)
                if canonical:
                    msg["canonical_chat_id"] = canonical
                messages.append(msg)
            # Track max date seen in this batch
            for m in messages:
                date_val = m.get("date")
                if date_val and (max_date_seen is None or date_val > max_date_seen):
                    max_date_seen = date_val
                canonical = m.get("canonical_chat_id")
                if canonical and date_val:
                    if canonical not in canonical_last_date or date_val > canonical_last_date[canonical]:
                        canonical_last_date[canonical] = date_val
            bulk_insert_messages(prepared_db_path, messages)

            processed += len(messages)
            max_rowid_seen = rows[-1][0]
            last_rowid = max_rowid_seen
    finally:
        conn.close()

    if processed > 0:
        set_last_processed_rowid(prepared_db_path, max_rowid_seen)
        if max_date_seen:
            set_last_processed_date(prepared_db_path, max_date_seen)
        if canonical_last_date:
            group_rows = []
            for canonical, last_date in canonical_last_date.items():
                group_rows.append(
                    {
                        "canonical_chat_id": canonical,
                        "chat_ids": canonical_members.get(canonical, []),
                        "member_count": len(set(canonical_members.get(canonical, []))),
                        "last_message_date": last_date,
                    }
                )
            bulk_upsert_chat_groups(prepared_db_path, group_rows)
    return processed


def get_source_max_date(source_db_path: str) -> Optional[str]:
    """Return max message date as ISO string (localtime) from source DB."""
    conn = sqlite3.connect(source_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT datetime(MAX(message.date)/1000000000 + strftime("%s","2001-01-01"), "unixepoch", "localtime")
            FROM message
            """
        )
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0])
        return None
    finally:
        conn.close()


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


def _build_canonical_map(source_db_path: str) -> (Dict[int, str], Dict[str, list]):
    """
    Build mapping chat_id -> canonical_chat_id and canonical -> chat_ids list.
    Canonical id is deterministic over normalized participant handles.
    """
    conn = sqlite3.connect(source_db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT chj.chat_id, h.id
            FROM chat_handle_join chj
            JOIN handle h ON chj.handle_id = h.ROWID
            """
        )
        chat_handles: Dict[int, set] = defaultdict(set)
        for chat_id, handle in cur.fetchall():
            norm = normalize_handle(handle)
            if norm:
                chat_handles[int(chat_id)].add(norm)

        chat_to_canonical: Dict[int, str] = {}
        canonical_members: Dict[str, list] = defaultdict(list)
        for cid, handles in chat_handles.items():
            if handles:
                canonical = "canon:" + ",".join(sorted(handles))
            else:
                canonical = f"canon:chat:{cid}"
            chat_to_canonical[cid] = canonical
            canonical_members[canonical].append(cid)

        return chat_to_canonical, canonical_members
    finally:
        conn.close()


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

