"""Optimized SQL queries for on-demand data extraction from chat.db."""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from . import prepared_messages as pm
from .contacts_provider import get_contact_info_by_handle, is_available as contacts_available
from .message_parsing import add_parsed_text_columns
from .time_utils import convert_to_apple_timestamp

logger = logging.getLogger(__name__)


def get_user_db_path() -> Optional[str]:
    """
    Get the Messages database path for the current user.

    Returns the standard macOS Messages database path.
    For single-user setup, this is always ~/Library/Messages/chat.db
    """
    # Standard macOS Messages database path
    default_path = os.path.expanduser("~/Library/Messages/chat.db")

    if os.path.exists(default_path):
        try:
            # Test database access
            with sqlite3.connect(default_path) as conn:
                conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
            return default_path
        except Exception as exc:
            logger.warning(f"Messages database exists but cannot be accessed: {exc}")
            return None

    return None


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
        except Exception as exc:
            logger.warning(f"Prepared DB read failed, falling back to source DB: {exc}")

    # Normalize order param
    order = order.lower()
    if order not in ("asc", "desc"):
        order = "desc"

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

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    df = add_parsed_text_columns(df, use_cache=True)

    # Apply search filtering on parsed final_text to catch attributedBody content
    if search:
        search_lower = str(search).lower()
        df = df[
            df["final_text"].astype(str).str.lower().str.contains(search_lower, na=False)
            | df["text"].astype(str).str.lower().str.contains(search_lower, na=False)
        ]

    # Re-sort and apply offset/limit in Python after filtering
    df = df.sort_values(by="date_utc", ascending=(order == "asc"))
    df = df.iloc[offset : offset + limit]

    messages = []

    for _, row in df.iterrows():
        text = row["final_text"]
        if not text:  # Skip if no text found
            continue

        # Get sender name/contact info
        if bool(row["is_from_me"]):
            sender_name = "You"
            sender_full_name = "You"
            sender_first_name = None
            sender_last_name = None
            sender_unique_id = None
        else:
            sender_contact = row["sender_contact"] if pd.notna(row["sender_contact"]) else None
            if sender_contact and contacts_available():
                # Try to get contact info from AddressBook
                contact_info = get_contact_info_by_handle(str(sender_contact))
                if contact_info and contact_info.get("full_name"):
                    sender_name = contact_info["full_name"]
                    sender_full_name = contact_info["full_name"]
                    sender_first_name = contact_info.get("first_name")
                    sender_last_name = contact_info.get("last_name")
                    sender_unique_id = contact_info.get("unique_id")
                    logger.debug(
                        "Found contact info for %s: %s (unique_id: %s)",
                        sender_contact,
                        sender_full_name,
                        sender_unique_id,
                    )
                else:
                    # Fallback to handle ID (phone/email)
                    sender_name = str(sender_contact)
                    sender_full_name = str(sender_contact)
                    sender_first_name = None
                    sender_last_name = None
                    sender_unique_id = None
                    logger.debug("No contact info found for %s", sender_contact)
            else:
                sender_name = str(sender_contact) if sender_contact else "Unknown"
                sender_full_name = sender_name
                sender_first_name = None
                sender_last_name = None
                sender_unique_id = None

        messages.append(
            {
                "text": text,
                "is_from_me": bool(row["is_from_me"]),
                "sender_name": sender_name,
                "sender_full_name": sender_full_name,
                "sender_first_name": sender_first_name,
                "sender_last_name": sender_last_name,
                "sender_unique_id": sender_unique_id,
                "date": row["date_utc"],
            }
        )

    return messages


def get_chat_list(db_path: str, prepared_db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get list of all chats with basic statistics.
    Fast query - no message processing needed.
    """
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

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn)

    # Don't deduplicate - show all chat entries so user can choose
    # Group by chat_identifier to identify potential duplicates
    df = df.sort_values("message_count", ascending=False)

    results = []
    for _, row in df.iterrows():
        # Get recent messages for this chat (available in details view)
        recent_messages = get_recent_messages_for_chat(
            db_path,
            int(row["chat_id"]),
            limit=5,
            prepared_db_path=prepared_db_path,
        )

        member_count_val = int(row["member_count"]) if pd.notna(row["member_count"]) else 0
        name_val = (
            row["chat_identifier"]
            if member_count_val == 1
            else (row["display_name"] or row["chat_identifier"])
        )
        results.append(
            {
                "chat_id": int(row["chat_id"]),
                "name": name_val,
                "chat_identifier": row["chat_identifier"],
                "members": member_count_val,
                "total_messages": int(row["message_count"]),
                "user_messages": int(row["user_message_count"])
                if pd.notna(row["user_message_count"])
                else 0,
                "last_message_date": row["last_message_date"],
                "recent_messages": recent_messages,  # Available but not shown in main table - shown in details view
            }
        )

    return results


def query_messages_with_urls(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str,
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
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)

    placeholders = ",".join(["?"] * len(chat_ids))
    # Query ALL messages in date range (not just those with text field)
    # We need to check attributedBody too, which requires parsing
    query = f"""
        SELECT 
            message.ROWID as message_id,
            message.text,
            message.attributedBody,
            message.date,
            message.is_from_me,
            message.handle_id,
            message.associated_message_type,
            handle.id as sender_contact,
            chat.display_name as chat_name,
            chat.ROWID as chat_id,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        JOIN chat ON chat_message_join.chat_id = chat.ROWID
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE 
            message.date BETWEEN ? AND ?
            AND chat.ROWID IN ({placeholders})
            AND (
                message.text IS NOT NULL 
                OR message.attributedBody IS NOT NULL
            )
            AND (
                message.associated_message_type IS NULL 
                OR message.associated_message_type = 0
            )
        ORDER BY message.date DESC
    """

    params = [start_ts, end_ts] + chat_ids
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return df

    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if "associated_message_type" in df.columns:
        df = df[df["associated_message_type"].isna() | (df["associated_message_type"] == 0)].copy()

    df = add_parsed_text_columns(df)

    # Filter to only messages with ANY URLs (http or https)
    url_pattern = r"https?://[^\s<>\"{}|\\^`\[\]]+"
    df["has_url"] = df["final_text"].astype(str).str.contains(
        url_pattern, case=False, na=False, regex=True
    )

    # Return only messages with URLs
    df_filtered = df[df["has_url"]].copy()

    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=["parsed_body", "has_url"])

    return df_filtered


def query_spotify_messages(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str,
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
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)

    placeholders = ",".join(["?"] * len(chat_ids))
    # Query ALL messages in date range (not just those with text field)
    # We need to check attributedBody too, which requires parsing
    query = f"""
        SELECT 
            message.ROWID as message_id,
            message.text,
            message.attributedBody,
            message.date,
            message.is_from_me,
            message.handle_id,
            message.associated_message_type,
            handle.id as sender_contact,
            chat.display_name as chat_name,
            chat.ROWID as chat_id,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        JOIN chat ON chat_message_join.chat_id = chat.ROWID
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE 
            message.date BETWEEN ? AND ?
            AND chat.ROWID IN ({placeholders})
            AND (
                message.text IS NOT NULL 
                OR message.attributedBody IS NOT NULL
            )
            AND (
                message.associated_message_type IS NULL 
                OR message.associated_message_type = 0
            )
        ORDER BY message.date DESC
    """

    params = [start_ts, end_ts] + chat_ids
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return df

    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if "associated_message_type" in df.columns:
        df = df[df["associated_message_type"].isna() | (df["associated_message_type"] == 0)].copy()

    df = add_parsed_text_columns(df)

    # Now filter to only messages with Spotify links in final_text
    spotify_pattern = r"https?://(open\.spotify\.com|spotify\.link)/[^\s<>\"{}|\\^`\[\]]+"
    df["has_spotify"] = df["final_text"].astype(str).str.contains(
        spotify_pattern, case=False, na=False, regex=True
    )

    # Return only messages with Spotify links
    df_filtered = df[df["has_spotify"]].copy()

    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=["parsed_body", "has_spotify"])

    return df_filtered


def query_all_messages_for_stats(
    db_path: str,
    chat_ids: List[int],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Query ALL messages from selected chats (by chat_id) and date range.
    Used for summary statistics (needs all messages, not just Spotify).

    Args:
        chat_ids: List of chat ROWIDs (not names) - more precise than names
    """
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)

    placeholders = ",".join(["?"] * len(chat_ids))
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
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    return df
