"""
Optimized SQL queries for on-demand data extraction from chat.db.
These queries filter at the database level instead of processing everything upfront.
Many helpers accept an optional prepared_db_path to reuse the prepared store
instead of reparsing attributedBody on every call.
"""
import os
import sqlite3
import pandas as pd
from typing import List, Optional, Dict, Any
import logging
from pathlib import Path

from contextlib import nullcontext
from . import parsing_utils as pu
from . import prepared_messages as pm
from . import query_builders as qb
from .handle_utils import normalize_handle, normalize_handle_variants
from .imessage_db import convert_to_apple_timestamp, db_connection, get_user_db_path
from ..contacts_data_processing.import_contact_info import get_contact_info_by_handle

logger = logging.getLogger(__name__)

# FTS imports - use try/except to handle if module not available
try:
    from .fts_indexer import (
        get_fts_db_path, 
        search_fts, 
        is_fts_available,
        populate_fts_database
    )
    FTS_AVAILABLE = True
except ImportError:
    FTS_AVAILABLE = False
    # Only log at debug level - FTS is optional, fallback works fine
    logger.debug("FTS indexer not available - will use fallback search method")

_message_body_cache = pu.MessageBodyCache(max_size=5000)


def _normalize_order(order: str) -> str:
    normalized = str(order or "").lower()
    return normalized if normalized in ("asc", "desc") else "desc"


def _get_participant_handles(db_path: str, chat_ids: List[int]) -> Dict[int, List[str]]:
    """Return mapping of chat_id -> participant handles (raw)."""
    if not chat_ids:
        return {}
    placeholders = qb.build_placeholders(len(chat_ids))
    query = f"""
        SELECT chj.chat_id, h.id
        FROM chat_handle_join chj
        JOIN handle h ON chj.handle_id = h.ROWID
        WHERE chj.chat_id IN ({placeholders})
    """
    with db_connection(db_path) as conn:
        rows = conn.execute(query, chat_ids).fetchall()
    mapping: Dict[int, List[str]] = {}
    for chat_id, handle in rows:
        mapping.setdefault(int(chat_id), []).append(str(handle))
    return mapping


def _fetch_chat_stats(
    conn: sqlite3.Connection,
    chat_ids: List[int],
    order_by: str = "last_message_date DESC",
    limit: Optional[int] = None,
) -> pd.DataFrame:
    if not chat_ids:
        return pd.DataFrame()
    placeholders = qb.build_placeholders(len(chat_ids))
    query = qb.chat_stats_query(placeholders, order_by=order_by, limit=limit)
    return pd.read_sql_query(query, conn, params=chat_ids)


def _group_chats_by_participants(
    db_path: str,
    rows: List[Dict[str, Any]],
    recent_messages_fetcher,
    recent_limit: int = 30,
) -> List[Dict[str, Any]]:
    """
    Group chats that have identical participant sets.
    recent_messages_fetcher: function(chat_id:int, limit:int) -> List[Dict]
    """
    if not rows:
        return []

    chat_ids = [r["chat_id"] for r in rows]
    participants_map = _get_participant_handles(db_path, chat_ids)

    groups: Dict[frozenset, List[Dict[str, Any]]] = {}
    for row in rows:
        handles = participants_map.get(row["chat_id"], [])
        norm_handles = [h for h in (normalize_handle(h) for h in handles) if h]
        key = frozenset(norm_handles) if norm_handles else frozenset({row["chat_id"]})
        groups.setdefault(key, []).append(row)

    grouped_results: List[Dict[str, Any]] = []
    for key, items in groups.items():
        if len(items) == 1:
            grouped_results.append(items[0])
            continue

        # Aggregate stats
        total_messages = sum(i.get("total_messages", 0) for i in items)
        user_messages = sum(i.get("user_messages", 0) for i in items)
        last_message_date = max((i.get("last_message_date") for i in items if i.get("last_message_date")), default=None)

        # Choose representative naming from item with most messages
        rep = max(items, key=lambda x: x.get("total_messages", 0))
        name_val = rep.get("name")
        chat_identifier = rep.get("chat_identifier")

        # member count: use max of reported or participant set size + self (best effort)
        member_count = max(
            [i.get("members", 0) for i in items] + [len(key) + 1 if key else 0]
        )

        # Merge recent messages across chats
        merged_recent: List[Dict[str, Any]] = []
        for i in items:
            cid = i["chat_id"]
            recent = recent_messages_fetcher(cid, recent_limit) or []
            merged_recent.extend(recent)
        merged_recent = sorted(
            merged_recent,
            key=lambda m: m.get("date"),
            reverse=True,
        )[:recent_limit]

        # Compute canonical id from participant key (stable)
        canonical_id = "canon:" + ",".join(sorted(key)) if key else f"canon:chat:{rep['chat_id']}"

        grouped_results.append(
            {
                **rep,
                "chat_id": rep["chat_id"],
                "chat_ids": [i["chat_id"] for i in items],
                "canonical_chat_id": canonical_id,
                "name": name_val,
                "chat_identifier": chat_identifier,
                "members": member_count,
                "total_messages": total_messages,
                "user_messages": user_messages,
                "last_message_date": last_message_date,
                "recent_messages": merged_recent,
            }
        )

    # Sort by message_count or last_message_date similar to original behavior
    return sorted(
        grouped_results,
        key=lambda r: (r.get("total_messages", 0), r.get("last_message_date") or ""),
        reverse=True,
    )


def _filter_chat_ids_by_content(
    conn: sqlite3.Connection,
    db_path: str,
    chat_ids: List[int],
    message_content: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    prepared_db_path: Optional[str] = None,
    max_messages: int = 10000,
) -> List[int]:
    """Filter chat ids by message content using prepared DB, FTS, or fallback parsing."""
    if not message_content or not chat_ids:
        return chat_ids

    filtered_chat_ids = list(chat_ids)
    use_prepared = bool(prepared_db_path and os.path.exists(prepared_db_path))

    if use_prepared:
        try:
            filtered_chat_ids = pm.filter_chat_ids_by_message_content(
                Path(prepared_db_path),  # type: ignore[arg-type]
                search_term=message_content,
                chat_ids=filtered_chat_ids,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning(f"Prepared DB content filter failed, falling back to source DB: {exc}")

    if not filtered_chat_ids:
        return []

    use_fts = False
    fts_db_path: Optional[str] = None
    if FTS_AVAILABLE:
        fts_db_path = get_fts_db_path(db_path)
        use_fts = is_fts_available(fts_db_path)

    if use_fts and fts_db_path:
        end_ts = convert_to_apple_timestamp(end_date) if end_date else None
        matching_messages = search_fts(
            fts_db_path=fts_db_path,
            search_term=message_content,
            chat_ids=filtered_chat_ids,
            start_date=start_date,
            end_date=end_ts,
            limit=max_messages,
        )

        if matching_messages.empty:
            return []
        valid_chat_ids_set = set(matching_messages['chat_id'].unique().tolist())
        return [cid for cid in filtered_chat_ids if cid in valid_chat_ids_set]

    # Fallback: parse attributedBody in source DB
    placeholders = qb.build_placeholders(len(filtered_chat_ids))
    message_check_query = f"""
        SELECT 
            chat.ROWID as chat_id,
            message.text,
            message.attributedBody,
            message.date
        FROM chat
        JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.ROWID IN ({placeholders})
        AND (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
        AND (message.associated_message_type IS NULL OR message.associated_message_type = 0)
    """

    params: List[Any] = list(filtered_chat_ids)
    adjusted_max = max_messages
    if start_date or end_date:
        adjusted_max = max(max_messages, 50000)
        if start_date and end_date:
            start_ts = convert_to_apple_timestamp(start_date)
            end_ts = convert_to_apple_timestamp(end_date)
            message_check_query += " AND message.date BETWEEN ? AND ?"
            params.extend([start_ts, end_ts])
        elif start_date:
            start_ts = convert_to_apple_timestamp(start_date)
            message_check_query += " AND message.date >= ?"
            params.append(start_ts)
        else:
            end_ts = convert_to_apple_timestamp(end_date)
            message_check_query += " AND message.date <= ?"
            params.append(end_ts)

    message_check_query += f" LIMIT {adjusted_max}"
    messages_df = pd.read_sql_query(message_check_query, conn, params=params)
    if messages_df.empty:
        return []

    valid_chat_ids_set = set()
    chunk_size = 1000
    for i in range(0, len(messages_df), chunk_size):
        chunk = messages_df.iloc[i:i + chunk_size].copy()
        chunk["parsed_body"] = chunk["attributedBody"].apply(pu.parse_attributed_body)
        chunk["final_text"] = chunk.apply(
            lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
            axis=1,
        )

        matching_chunk = chunk[
            chunk['final_text'].astype(str).str.contains(message_content, case=False, na=False)
        ]

        if not matching_chunk.empty:
            valid_chat_ids_set.update(matching_chunk['chat_id'].unique().tolist())

    if not valid_chat_ids_set:
        return []

    return [cid for cid in filtered_chat_ids if cid in valid_chat_ids_set]

def get_recent_messages_for_chat(
    db_path: str,
    chat_id: int,
    limit: int = 5,
    offset: int = 0,
    order: str = "desc",
    search: Optional[str] = None,
    prepared_db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get recent messages from a chat to help user identify which chat entry to use.
    Returns preview of most recent messages.
    
    Parses attributedBody for complete message text (not just text field).
    """
    # Prefer prepared store if available to avoid reparsing attributedBody
    if prepared_db_path and os.path.exists(prepared_db_path):
        try:
            prepared_messages = pm.get_recent_messages_prepared(
                Path(prepared_db_path),
                chat_id=chat_id,
                limit=limit,
                offset=offset,
                order=order,
                search=search,
            )
            return [
                {
                    "text": msg["text"],
                    "is_from_me": bool(msg["is_from_me"]),
                    "sender_name": msg.get("sender_handle") or "Unknown",
                    "sender_full_name": msg.get("sender_handle") or "Unknown",
                    "sender_first_name": None,
                    "sender_last_name": None,
                    "sender_unique_id": None,
                    "date": msg["date"],
                }
                for msg in prepared_messages
                if msg.get("text")
            ]
        except Exception as e:
            logger.warning(f"Prepared DB read failed, falling back to source DB: {e}")

    order = _normalize_order(order)

    # We fetch more rows than requested so search filtering (on parsed attributedBody)
    # still returns results, then slice in Python.
    query_limit = max(limit + offset + 200, 500 if search else 0)

    # Get messages with both text and attributedBody, including handle info for sender names
    query = f"""
        SELECT 
            message.ROWID as message_id,
            message.text,
            message.attributedBody,
            message.is_from_me,
            message.handle_id,
            handle.id as sender_contact,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE chat_message_join.chat_id = ?
        AND (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
        ORDER BY message.date {order.upper()}
        LIMIT ?
    """

    params: List[Any] = [chat_id, query_limit]
    with db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    # Parse attributedBody for messages that have it, with cache
    def parse_body(body, msg_id):
        return _message_body_cache.get_parsed(int(msg_id), body)

    df["parsed_body"] = [
        parse_body(body, msg_id) for body, msg_id in zip(df["attributedBody"], df["message_id"])
    ]
    
    # Create final_text (text field OR extracted from attributedBody)
    df["final_text"] = df.apply(
        lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
        axis=1,
    )
    
    # Apply search filtering on parsed final_text to catch attributedBody content
    if search:
        search_lower = str(search).lower()
        df = df[
            df['final_text'].astype(str).str.lower().str.contains(search_lower, na=False)
            | df['text'].astype(str).str.lower().str.contains(search_lower, na=False)
        ]
    
    # Re-sort and apply offset/limit in Python after filtering
    df = df.sort_values(by="date_utc", ascending=(order == "asc"))
    df = df.iloc[offset:offset + limit]
    
    messages = []
    # Import contact info function
    try:
        try:
            from ..contacts_data_processing.import_contact_info import get_contact_info_by_handle
        except ImportError:
            logger.debug("Could not import contact info function: contacts_data_processing module not available")
            get_contact_info_by_handle = None
        use_contact_info = get_contact_info_by_handle is not None
        if use_contact_info:
            logger.debug("Contact info import successful")
    except ImportError as e:
        logger.warning(f"Could not import contact info function: {e}")
        use_contact_info = False
    
    for _, row in df.iterrows():
        text = row['final_text']
        if not text:  # Skip if no text found
            continue
        
        # Get sender name/contact info
        if bool(row['is_from_me']):
            sender_name = "You"
            sender_full_name = "You"
            sender_first_name = None
            sender_last_name = None
            sender_unique_id = None
        else:
            sender_contact = row['sender_contact'] if pd.notna(row['sender_contact']) else None
            if use_contact_info and sender_contact:
                # Try to get contact info from AddressBook
                try:
                    contact_info = get_contact_info_by_handle(str(sender_contact))
                    if contact_info and contact_info.get('full_name'):
                        sender_name = contact_info['full_name']
                        sender_full_name = contact_info['full_name']
                        sender_first_name = contact_info.get('first_name')
                        sender_last_name = contact_info.get('last_name')
                        sender_unique_id = contact_info.get('unique_id')
                        logger.debug(f"Found contact info for {sender_contact}: {sender_full_name} (unique_id: {sender_unique_id})")
                    else:
                        # Fallback to handle ID (phone/email)
                        sender_name = str(sender_contact)
                        sender_full_name = str(sender_contact)
                        sender_first_name = None
                        sender_last_name = None
                        sender_unique_id = None
                        logger.debug(f"No contact info found for {sender_contact}")
                except Exception as e:
                    logger.warning(f"Error getting contact info for {sender_contact}: {e}")
                    sender_name = str(sender_contact)
                    sender_full_name = str(sender_contact)
                    sender_first_name = None
                    sender_last_name = None
                    sender_unique_id = None
            else:
                sender_name = str(sender_contact) if sender_contact else "Unknown"
                sender_full_name = sender_name
                sender_first_name = None
                sender_last_name = None
                sender_unique_id = None
        
        # Don't truncate - let frontend handle display formatting
        # Frontend will show preview with proper styling
        messages.append({
            "text": text,
            "is_from_me": bool(row['is_from_me']),
            "sender_name": sender_name,
            "sender_full_name": sender_full_name,
            "sender_first_name": sender_first_name,
            "sender_last_name": sender_last_name,
            "sender_unique_id": sender_unique_id,
            "date": row['date_utc']
        })
    
    return messages

def get_chat_list(db_path: str, prepared_db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get list of all chats with basic statistics.
    Fast query - no message processing needed.
    """
    prepared_ctx = db_connection(prepared_db_path) if prepared_db_path and os.path.exists(prepared_db_path) else nullcontext()
    
    query = """
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            COUNT(DISTINCT message.ROWID) as message_count,
            -- Participant count: distinct handles from chat_handle_join + self if present
            (
              COUNT(DISTINCT chat_handle_join.handle_id)
              + CASE WHEN SUM(CASE WHEN message.is_from_me = 1 THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END
            ) AS member_count,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        LEFT JOIN chat_handle_join ON chat.ROWID = chat_handle_join.chat_id
        WHERE chat.display_name IS NOT NULL
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier
        HAVING message_count > 0
        ORDER BY last_message_date DESC
    """
    with db_connection(db_path) as conn, prepared_ctx as prepared_conn:
        df = pd.read_sql_query(query, conn)
    
    # Don't deduplicate - show all chat entries so user can choose
    # Group by chat_identifier to identify potential duplicates
    df = df.sort_values('message_count', ascending=False)
    
    results = []
    for _, row in df.iterrows():
        chat_id_val = int(row["chat_id"])

        # Resolve participant handles (excluding "self" is fine because chat_handle_join stores others)
        participant_handles: List[str] = []
        try:
            with db_connection(db_path) as c2:
                cur = c2.cursor()
                cur.execute(
                    """
                    SELECT h.id
                    FROM chat_handle_join chj
                    JOIN handle h ON chj.handle_id = h.ROWID
                    WHERE chj.chat_id = ?
                    """,
                    (chat_id_val,),
                )
                participant_handles = [r[0] for r in cur.fetchall() if r and r[0]]
        except Exception:
            participant_handles = []

        def prepared_lookup(name_handle: str) -> Optional[str]:
            """Try both raw and digits-only against contacts.display_name."""
            if not prepared_conn:
                return None
            try:
                curp = prepared_conn.cursor()
                for h in {name_handle, "".join(ch for ch in name_handle if ch.isdigit())}:
                    if not h:
                        continue
                    curp.execute(
                        "SELECT display_name FROM contacts WHERE contact_info = ? LIMIT 1",
                        (h,),
                    )
                    rowp = curp.fetchone()
                    if rowp and rowp[0]:
                        return str(rowp[0])
            except Exception:
                pass
            return None

        # Helper to resolve a display name for a handle
        def resolve_name(handle: str) -> str:
            if not handle:
                return ""
            for h in normalize_handle_variants(handle):
                disp = prepared_lookup(h)
                if disp:
                    return disp
                try:
                    info = get_contact_info_by_handle(h)
                    if info and info.get("full_name"):
                        return info["full_name"]
                except Exception:
                    pass
            return str(handle)

        def resolve_first_name(handle: str) -> str:
            if not handle:
                return ""
            for h in normalize_handle_variants(handle):
                disp = prepared_lookup(h)
                if disp:
                    disp = disp.strip()
                    if disp:
                        return disp.split(" ")[0]
                try:
                    info = get_contact_info_by_handle(h)
                    if info:
                        if info.get("first_name"):
                            return info["first_name"]
                        if info.get("full_name"):
                            return str(info["full_name"]).split(" ")[0]
                except Exception:
                    pass
            return str(handle)

        participant_names = [resolve_name(h) for h in participant_handles if h]
        participant_names = [n for n in participant_names if n]
        participant_first_names = [resolve_first_name(h) for h in participant_handles if h]
        participant_first_names = [n for n in participant_first_names if n]

        # Get recent messages for this chat (available in details view)
        recent_messages = get_recent_messages_for_chat(
            db_path,
            chat_id_val,
            limit=5,
            prepared_db_path=prepared_db_path,
        )
        
        member_count_val = int(row['member_count']) if pd.notna(row['member_count']) else 0
        # If no display name, build one from participants (excluding self is implied by chat_handle_join)
        if member_count_val > 1 and (row['display_name'] is None or str(row['display_name']).strip() == ""):
            # Use up to 3 participant names to keep it short
            display_pool = participant_first_names if participant_first_names else participant_names
            name_val = ", ".join(display_pool[:3]) if display_pool else (row['chat_identifier'] or "Unnamed Chat")
        else:
            name_val = row['chat_identifier'] if member_count_val == 1 else (row['display_name'] or row['chat_identifier'])

        results.append({
            "chat_id": chat_id_val,
            "chat_ids": [chat_id_val],
            "name": name_val,
            "chat_identifier": row['chat_identifier'],
            "members": member_count_val,
            "total_messages": int(row['message_count']),
            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
            "last_message_date": row['last_message_date'],
            "recent_messages": recent_messages  # Available but not shown in main table - shown in details view
        })
    
    # Group chats with identical participants
    return _group_chats_by_participants(
        db_path,
        results,
        lambda cid, limit: get_recent_messages_for_chat(
            db_path,
            cid,
            limit=limit,
            prepared_db_path=prepared_db_path,
        ),
        recent_limit=30,
    )

def query_messages_with_urls(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Query ALL messages with ANY URLs (not just Spotify) from selected chats (by chat_id) and date range.
    This is used to find Apple Music, YouTube, Instagram, and other links in addition to Spotify.
    
    This function handles both text and attributedBody fields:
    - For messages with text field: uses SQL LIKE
    - For messages with attributedBody (binary): loads into memory and parses using typedstream
    
    Args:
        chat_ids: List of chat ROWIDs (not names) - more precise than names
    """
    if not chat_ids:
        return pd.DataFrame()

    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    placeholders = qb.build_placeholders(len(chat_ids))
    query = qb.messages_with_body_query(placeholders)
    
    params = [start_ts, end_ts] + chat_ids
    with db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    if df.empty:
        return df
    
    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if 'associated_message_type' in df.columns:
        df = df[df['associated_message_type'].isna() | (df['associated_message_type'] == 0)].copy()
    
    # Parse attributedBody for messages that have it
    # This extracts text from the binary field
    df["parsed_body"] = df["attributedBody"].apply(pu.parse_attributed_body)

    # Create final_text column (text field OR extracted from attributedBody)
    df["final_text"] = df.apply(
        lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
        axis=1,
    )
    
    # Filter to only messages with ANY URLs (http or https)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    df["has_url"] = df["final_text"].astype(str).str.contains(url_pattern, case=False, na=False, regex=True)
    
    # Return only messages with URLs
    df_filtered = df[df['has_url']].copy()
    
    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=["parsed_body", "has_url"])
    
    return df_filtered

def query_spotify_messages(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Query messages with Spotify links from selected chats (by chat_id) and date range.
    Only returns messages that contain Spotify links.
    
    This function handles both text and attributedBody fields:
    - For messages with text field: uses SQL LIKE
    - For messages with attributedBody (binary): loads into memory and parses using typedstream
    
    Args:
        chat_ids: List of chat ROWIDs (not names) - more precise than names
    """
    if not chat_ids:
        return pd.DataFrame()

    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    placeholders = qb.build_placeholders(len(chat_ids))
    query = qb.messages_with_body_query(placeholders)
    
    params = [start_ts, end_ts] + chat_ids
    with db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)
    
    if df.empty:
        return df
    
    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if 'associated_message_type' in df.columns:
        df = df[df['associated_message_type'].isna() | (df['associated_message_type'] == 0)].copy()
    
    # Parse attributedBody for messages that have it
    df["parsed_body"] = df["attributedBody"].apply(pu.parse_attributed_body)
    
    # Create final_text column (text field OR extracted from attributedBody)
    df["final_text"] = df.apply(
        lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
        axis=1,
    )
    
    # Now filter to only messages with Spotify links in final_text
    spotify_pattern = r'https?://(open\.spotify\.com|spotify\.link)/[^\s<>"{}|\\^`\[\]]+'
    df["has_spotify"] = df["final_text"].astype(str).str.contains(spotify_pattern, case=False, na=False, regex=True)
    
    # Return only messages with Spotify links
    df_filtered = df[df['has_spotify']].copy()
    
    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=["parsed_body", "has_spotify"])
    
    return df_filtered

def query_all_messages_for_stats(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Query ALL messages from selected chats (by chat_id) and date range.
    Used for summary statistics (needs all messages, not just Spotify).
    
    Args:
        chat_ids: List of chat ROWIDs (not names) - more precise than names
    """
    if not chat_ids:
        return pd.DataFrame()

    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    placeholders = qb.build_placeholders(len(chat_ids))
    query = f"""
        SELECT 
            message.ROWID as message_id,
            message.text,
            message.date,
            message.is_from_me,
            message.attributedBody,
            message.handle_id,
            chat.display_name as chat_name,
            chat.ROWID as chat_id,
            CASE 
                WHEN message.is_from_me = 1 THEN 1 
                ELSE message.handle_id 
            END as sender_handle_id,
            handle.id as contact_info
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        JOIN chat ON chat_message_join.chat_id = chat.ROWID
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE 
            message.date BETWEEN ? AND ?
            AND chat.ROWID IN ({placeholders})
        ORDER BY message.date DESC
    """
    
    params = [start_ts, end_ts] + chat_ids
    with db_connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)

def search_chats_by_name(db_path: str, query: str) -> List[Dict[str, Any]]:
    """
    Search chats by name, identifier, or member names.
    Fast query for chat search functionality.
    
    Searches across:
    - Chat display name
    - Chat identifier (phone numbers, email addresses)
    - Member phone numbers/emails (via handle table)
    - Member contact names (via Contacts database)
    """
    search_pattern = f'%{query}%'

    with db_connection(db_path) as conn:
        handle_query = """
            SELECT DISTINCT handle.ROWID as handle_id
            FROM handle
            WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
        """
        handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
        handle_ids = handle_matches['handle_id'].tolist() if not handle_matches.empty else []

        try:
            from ..contacts_data_processing.import_contact_info import get_contact_info_by_handle

            # Use the in-memory contact cache to search by name parts.
            # get_contact_info_by_handle will load the cache on first call.
            # We search handles already found and look for matching contact names.
            # This is a lighter approach than querying the AddressBook DB directly.
        except Exception as e:
            logger.debug(f"Could not search Contacts database: {e}")

        if handle_ids:
            handle_placeholders = qb.build_placeholders(len(handle_ids))
            search_query = f"""
                SELECT DISTINCT chat.ROWID as chat_id
                FROM chat
                WHERE (
                    chat.display_name LIKE ?
                    OR chat.chat_identifier LIKE ?
                )
                UNION
                SELECT DISTINCT chat.ROWID as chat_id
                FROM chat
                JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                JOIN message ON chat_message_join.message_id = message.ROWID
                WHERE message.handle_id IN ({handle_placeholders})
            """
            params = [search_pattern, search_pattern] + handle_ids
        else:
            search_query = """
                SELECT DISTINCT chat.ROWID as chat_id
                FROM chat
                WHERE (
                    chat.display_name LIKE ?
                    OR chat.chat_identifier LIKE ?
                )
            """
            params = [search_pattern, search_pattern]

        matching_chats = pd.read_sql_query(search_query, conn, params=params)
        if matching_chats.empty:
            return []

        chat_ids = matching_chats['chat_id'].tolist()
        df = _fetch_chat_stats(conn, chat_ids, order_by="last_message_date DESC", limit=50)

    if df.empty:
        return []

    df = df.sort_values('message_count', ascending=False)

    results = []
    for _, row in df.iterrows():
        recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)

        member_count_val = int(row['member_count']) if pd.notna(row['member_count']) else 0
        name_val = row['chat_identifier'] if member_count_val == 1 else (row['display_name'] or row['chat_identifier'])
        results.append({
            "chat_id": int(row['chat_id']),
            "chat_ids": [int(row["chat_id"])],
            "name": name_val,
            "chat_identifier": row['chat_identifier'],
            "members": member_count_val,
            "total_messages": int(row['message_count']),
            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
            "last_message_date": row['last_message_date'],
            "recent_messages": recent_messages
        })

    return _group_chats_by_participants(
        db_path,
        results,
        lambda cid, limit: get_recent_messages_for_chat(
            db_path,
            cid,
            limit=limit,
            prepared_db_path=None,
        ),
        recent_limit=30,
    )

def advanced_chat_search(
    db_path: str,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[List[str]] = None,
    message_content: Optional[str] = None,
    limit_to_recent: Optional[int] = None,
    prepared_db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Advanced chat search with multiple filter criteria:
    - Text query (chat name, identifier, or participant)
    - Date range (messages within this range)
    - Participants (people in the chat)
    - Message content (specific words in messages)
    
    Returns chats that match ALL specified criteria.
    """
    logger.info(
        "advanced_chat_search called: query=%s, start_date=%s, end_date=%s, message_content=%s",
        query,
        start_date,
        end_date,
        message_content,
    )

    chat_ids: List[int] = []

    with db_connection(db_path) as conn:
        # Step 1: Find handle IDs for participant search
        participant_handle_ids: List[int] = []
        if participant_names:
            for name in participant_names:
                handle_query = """
                    SELECT DISTINCT handle.ROWID as handle_id
                    FROM handle
                    WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
                """
                search_pattern = f'%{name}%'
                handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
                if not handle_matches.empty:
                    participant_handle_ids.extend(handle_matches['handle_id'].tolist())

                try:
                    from ..contacts_data_processing.import_contact_info import get_contact_info_by_handle
                    # Contact search via in-memory cache is handled above through handle LIKE matching.
                except Exception as exc:
                    logger.debug(f"Could not search Contacts database: {exc}")

            participant_handle_ids = list(set(participant_handle_ids))

        # Step 2: Build query to find matching chat IDs based on message criteria
        message_conditions: List[str] = []
        message_params: List[Any] = []

        if start_date or end_date:
            if start_date and end_date:
                start_ts = convert_to_apple_timestamp(start_date)
                end_ts = convert_to_apple_timestamp(end_date)
                message_conditions.append("message.date BETWEEN ? AND ?")
                message_params.extend([start_ts, end_ts])
            elif start_date:
                start_ts = convert_to_apple_timestamp(start_date)
                message_conditions.append("message.date >= ?")
                message_params.append(start_ts)
            elif end_date:
                end_ts = convert_to_apple_timestamp(end_date)
                message_conditions.append("message.date <= ?")
                message_params.append(end_ts)

        if participant_handle_ids:
            handle_placeholders = qb.build_placeholders(len(participant_handle_ids))
            message_conditions.append(f"message.handle_id IN ({handle_placeholders})")
            message_params.extend(participant_handle_ids)

        if message_conditions:
            message_conditions.append("(message.text IS NOT NULL OR message.attributedBody IS NOT NULL)")
            message_conditions.append("(message.associated_message_type IS NULL OR message.associated_message_type = 0)")

        if message_content and not (start_date or end_date or participant_handle_ids):
            matching_chats = pd.read_sql_query("SELECT DISTINCT chat.ROWID as chat_id FROM chat", conn)
            chat_ids = matching_chats['chat_id'].tolist() if not matching_chats.empty else []
        elif message_conditions:
            message_where = " AND ".join(message_conditions)
            chat_id_query = f"""
                SELECT DISTINCT chat.ROWID as chat_id
                FROM chat
                JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                JOIN message ON chat_message_join.message_id = message.ROWID
                WHERE {message_where}
            """
            matching_chats = pd.read_sql_query(chat_id_query, conn, params=message_params)
            if matching_chats.empty:
                return []
            chat_ids = matching_chats['chat_id'].tolist()
        else:
            matching_chats = pd.read_sql_query("SELECT DISTINCT chat.ROWID as chat_id FROM chat", conn)
            chat_ids = matching_chats['chat_id'].tolist() if not matching_chats.empty else []

        # Step 3: Limit to most recent chats if specified
        if limit_to_recent is not None and chat_ids and len(chat_ids) > limit_to_recent:
            chat_id_placeholders = qb.build_placeholders(len(chat_ids))
            recent_query = f"""
                SELECT DISTINCT chat.ROWID as chat_id,
                       MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
                FROM chat
                LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                LEFT JOIN message ON chat_message_join.message_id = message.ROWID
                WHERE chat.ROWID IN ({chat_id_placeholders})
                GROUP BY chat.ROWID
                ORDER BY last_message_date DESC
                LIMIT {limit_to_recent}
            """
            recent_chats = pd.read_sql_query(recent_query, conn, params=chat_ids)
            chat_ids = recent_chats['chat_id'].tolist() if not recent_chats.empty else chat_ids[:limit_to_recent]

        # Step 4: Filter by message content (prepared DB -> FTS -> fallback)
        chat_ids = _filter_chat_ids_by_content(
            conn,
            db_path,
            chat_ids,
            message_content,
            start_date,
            end_date,
            prepared_db_path=prepared_db_path,
            max_messages=10000,
        )
        if not chat_ids:
            return []

        # Step 4b: Apply text query filter (chat name, identifier) if provided
        if query:
            search_pattern = f'%{query}%'
            chat_id_placeholders = qb.build_placeholders(len(chat_ids)) if chat_ids else "NULL"

            if chat_ids:
                filter_query = f"""
                    SELECT DISTINCT chat.ROWID as chat_id
                    FROM chat
                    WHERE chat.ROWID IN ({chat_id_placeholders})
                    AND (chat.display_name LIKE ? OR chat.chat_identifier LIKE ?)
                """
                filtered_chats = pd.read_sql_query(filter_query, conn, params=chat_ids + [search_pattern, search_pattern])
            else:
                filter_query = """
                    SELECT DISTINCT chat.ROWID as chat_id
                    FROM chat
                    WHERE chat.display_name LIKE ? OR chat.chat_identifier LIKE ?
                """
                filtered_chats = pd.read_sql_query(filter_query, conn, params=[search_pattern, search_pattern])

            if filtered_chats.empty:
                return []

            chat_ids = filtered_chats['chat_id'].tolist()

        if not chat_ids:
            return []

        # Step 5: Get full statistics for matching chats (same as search_chats_by_name)
        df = _fetch_chat_stats(conn, chat_ids, order_by="message_count DESC", limit=100)

    if df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)

        member_count_val = int(row['member_count']) if pd.notna(row['member_count']) else 0
        name_val = row['chat_identifier'] if member_count_val == 1 else (row['display_name'] or row['chat_identifier'])
        results.append({
            "chat_id": int(row['chat_id']),
            "name": name_val,
            "chat_identifier": row['chat_identifier'],
            "members": member_count_val,
            "total_messages": int(row['message_count']),
            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
            "last_message_date": row['last_message_date'],
            "recent_messages": recent_messages
        })

    return results

def advanced_chat_search_streaming(
    db_path: str,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[List[str]] = None,
    message_content: Optional[str] = None,
    limit_to_recent: Optional[int] = None,
    prepared_db_path: Optional[str] = None,
):
    """
    Streaming version of advanced_chat_search that yields results as they're found.
    Processes chats in batches and yields results incrementally.
    Limits to most recent chats by default.
    """
    try:
        with db_connection(db_path) as conn:
            participant_handle_ids: List[int] = []
            if participant_names:
                for name in participant_names:
                    handle_query = """
                        SELECT DISTINCT handle.ROWID as handle_id
                        FROM handle
                        WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
                    """
                    search_pattern = f'%{name}%'
                    handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
                    if not handle_matches.empty:
                        participant_handle_ids.extend(handle_matches['handle_id'].tolist())

                participant_handle_ids = list(set(participant_handle_ids))

            message_conditions: List[str] = []
            message_params: List[Any] = []

            if start_date or end_date:
                if start_date and end_date:
                    start_ts = convert_to_apple_timestamp(start_date)
                    end_ts = convert_to_apple_timestamp(end_date)
                    message_conditions.append("message.date BETWEEN ? AND ?")
                    message_params.extend([start_ts, end_ts])
                elif start_date:
                    start_ts = convert_to_apple_timestamp(start_date)
                    message_conditions.append("message.date >= ?")
                    message_params.append(start_ts)
                elif end_date:
                    end_ts = convert_to_apple_timestamp(end_date)
                    message_conditions.append("message.date <= ?")
                    message_params.append(end_ts)

            if participant_handle_ids:
                handle_placeholders = qb.build_placeholders(len(participant_handle_ids))
                message_conditions.append(f"message.handle_id IN ({handle_placeholders})")
                message_params.extend(participant_handle_ids)

            if message_conditions:
                message_conditions.append("(message.text IS NOT NULL OR message.attributedBody IS NOT NULL)")
                message_conditions.append("(message.associated_message_type IS NULL OR message.associated_message_type = 0)")

            if message_content and not (start_date or end_date or participant_handle_ids):
                all_chats = pd.read_sql_query("SELECT DISTINCT chat.ROWID as chat_id FROM chat", conn)
                chat_ids = all_chats['chat_id'].tolist() if not all_chats.empty else []
            elif message_conditions:
                message_where = " AND ".join(message_conditions)
                chat_id_query = f"""
                    SELECT DISTINCT chat.ROWID as chat_id
                    FROM chat
                    JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                    JOIN message ON chat_message_join.message_id = message.ROWID
                    WHERE {message_where}
                """
                matching_chats = pd.read_sql_query(chat_id_query, conn, params=message_params)
                chat_ids = matching_chats['chat_id'].tolist() if not matching_chats.empty else []
            else:
                all_chats = pd.read_sql_query("SELECT DISTINCT chat.ROWID as chat_id FROM chat", conn)
                chat_ids = all_chats['chat_id'].tolist() if not all_chats.empty else []

            if limit_to_recent and chat_ids and len(chat_ids) > limit_to_recent:
                chat_id_placeholders = qb.build_placeholders(len(chat_ids))
                recent_query = f"""
                    SELECT DISTINCT chat.ROWID as chat_id,
                           MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
                    FROM chat
                    LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                    LEFT JOIN message ON chat_message_join.message_id = message.ROWID
                    WHERE chat.ROWID IN ({chat_id_placeholders})
                    GROUP BY chat.ROWID
                    ORDER BY last_message_date DESC
                    LIMIT {limit_to_recent}
                """
                recent_chats = pd.read_sql_query(recent_query, conn, params=chat_ids)
                chat_ids = recent_chats['chat_id'].tolist() if not recent_chats.empty else chat_ids[:limit_to_recent]

            if query and chat_ids:
                search_pattern = f'%{query}%'
                chat_id_placeholders = qb.build_placeholders(len(chat_ids))
                filter_query = f"""
                    SELECT DISTINCT chat.ROWID as chat_id
                    FROM chat
                    WHERE chat.ROWID IN ({chat_id_placeholders})
                    AND (chat.display_name LIKE ? OR chat.chat_identifier LIKE ?)
                """
                filtered_chats = pd.read_sql_query(filter_query, conn, params=chat_ids + [search_pattern, search_pattern])
                chat_ids = filtered_chats['chat_id'].tolist() if not filtered_chats.empty else []

            chat_ids = _filter_chat_ids_by_content(
                conn,
                db_path,
                chat_ids,
                message_content,
                start_date,
                end_date,
                prepared_db_path=prepared_db_path,
                max_messages=5000,
            )

            if not chat_ids:
                return

            BATCH_SIZE = 10
            for i in range(0, len(chat_ids), BATCH_SIZE):
                batch_chat_ids = chat_ids[i:i + BATCH_SIZE]
                df = _fetch_chat_stats(conn, batch_chat_ids, order_by="last_message_date DESC")

                for _, row in df.iterrows():
                    try:
                        recent_messages = get_recent_messages_for_chat(
                            db_path,
                            int(row["chat_id"]),
                            limit=5,
                            prepared_db_path=prepared_db_path,
                        )

                        member_count_val = int(row['member_count']) if pd.notna(row['member_count']) else 0
                        name_val = row['chat_identifier'] if member_count_val == 1 else (row['display_name'] or row['chat_identifier'])
                        result = {
                            "chat_id": int(row['chat_id']),
                            "name": name_val,
                            "chat_identifier": row['chat_identifier'],
                            "members": member_count_val,
                            "total_messages": int(row['message_count']),
                            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
                            "last_message_date": row['last_message_date'],
                            "recent_messages": recent_messages
                        }

                        yield result
                    except Exception as exc:
                        logger.error(f"Error processing chat {row.get('chat_id', 'unknown')}: {exc}", exc_info=True)
                        continue

    except Exception as exc:
        logger.error(f"Error in advanced_chat_search_streaming: {exc}", exc_info=True)
        raise
