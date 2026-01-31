"""
Thin wrapper around existing iMessage query functions.
Returns JSON-serializable dicts for MCP tool responses.
"""

import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Add the packages directory to path so 'dopetracks' can be imported as a package
PACKAGES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if PACKAGES_PATH not in sys.path:
    sys.path.insert(0, PACKAGES_PATH)

from dopetracks.processing.imessage_data_processing.imessage_db import (
    db_connection,
    get_user_db_path,
    convert_to_apple_timestamp,
)
from dopetracks.processing.imessage_data_processing.optimized_queries import (
    get_chat_list,
    search_chats_by_name,
    get_recent_messages_for_chat,
    query_spotify_messages,
)
from dopetracks.processing.imessage_data_processing.parsing_utils import (
    extract_spotify_urls,
    finalize_text,
    parse_attributed_body,
)


def get_db_path() -> str:
    """Get the iMessage database path, raising if not accessible."""
    path = get_user_db_path()
    if not path:
        raise RuntimeError(
            "Cannot access iMessage database. "
            "Grant Full Disk Access in System Preferences > Security & Privacy > Privacy."
        )
    return path


def list_chats(limit: int = 50) -> List[Dict[str, Any]]:
    """
    List all chats with basic statistics.

    Returns a list of chat dicts with: chat_id, name, members, total_messages, last_message_date
    """
    db_path = get_db_path()
    chats = get_chat_list(db_path)

    # Simplify for MCP response
    result = []
    for chat in chats[:limit]:
        result.append({
            "chat_id": chat["chat_id"],
            "chat_ids": chat.get("chat_ids", [chat["chat_id"]]),
            "name": chat.get("name") or chat.get("chat_identifier") or "Unknown",
            "members": chat.get("members", 0),
            "total_messages": chat.get("total_messages", 0),
            "last_message_date": chat.get("last_message_date"),
        })
    return result


def search_chats(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search chats by name, identifier, or participant.

    Returns matching chats with basic info.
    """
    db_path = get_db_path()
    chats = search_chats_by_name(db_path, query)

    result = []
    for chat in chats[:limit]:
        result.append({
            "chat_id": chat["chat_id"],
            "chat_ids": chat.get("chat_ids", [chat["chat_id"]]),
            "name": chat.get("name") or chat.get("chat_identifier") or "Unknown",
            "members": chat.get("members", 0),
            "total_messages": chat.get("total_messages", 0),
            "last_message_date": chat.get("last_message_date"),
        })
    return result


def get_messages(
    chat_id: int,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get messages from a chat with optional date filtering.

    Args:
        chat_id: The chat ROWID
        limit: Max messages to return
        offset: Pagination offset
        start_date: ISO date string for start of range
        end_date: ISO date string for end of range
        search: Optional text search filter

    Returns list of message dicts with: text, sender_name, date, is_from_me
    """
    db_path = get_db_path()

    # If date filtering is requested, we need to use SQL directly
    if start_date or end_date:
        return _get_messages_with_date_filter(
            db_path, chat_id, limit, offset, start_date, end_date, search
        )

    # Simple case: use existing function
    messages = get_recent_messages_for_chat(
        db_path, chat_id, limit=limit, offset=offset, search=search
    )

    return [
        {
            "text": msg.get("text", ""),
            "sender_name": msg.get("sender_name", "Unknown"),
            "date": msg.get("date"),
            "is_from_me": msg.get("is_from_me", False),
        }
        for msg in messages
    ]


def _get_messages_with_date_filter(
    db_path: str,
    chat_id: int,
    limit: int,
    offset: int,
    start_date: Optional[str],
    end_date: Optional[str],
    search: Optional[str],
) -> List[Dict[str, Any]]:
    """Get messages with date filtering using direct SQL."""
    import pandas as pd

    conditions = ["chat_message_join.chat_id = ?"]
    params: List[Any] = [chat_id]

    if start_date:
        start_ts = convert_to_apple_timestamp(start_date)
        conditions.append("message.date >= ?")
        params.append(start_ts)

    if end_date:
        end_ts = convert_to_apple_timestamp(end_date)
        conditions.append("message.date <= ?")
        params.append(end_ts)

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            message.ROWID as message_id,
            message.text,
            message.attributedBody,
            message.is_from_me,
            handle.id as sender_contact,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE {where_clause}
        AND (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
        ORDER BY message.date DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit + 200, offset])  # Fetch extra for search filtering

    with db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return []

    # Parse attributedBody
    df["parsed_body"] = df["attributedBody"].apply(parse_attributed_body)
    df["final_text"] = df.apply(
        lambda row: finalize_text(row["text"], row["parsed_body"]),
        axis=1,
    )

    # Apply search filter
    if search:
        search_lower = search.lower()
        df = df[df["final_text"].str.lower().str.contains(search_lower, na=False)]

    # Slice to requested limit
    df = df.iloc[:limit]

    messages = []
    for _, row in df.iterrows():
        text = row["final_text"]
        if not text:
            continue

        sender_name = "You" if row["is_from_me"] else (row["sender_contact"] or "Unknown")

        messages.append({
            "text": text,
            "sender_name": sender_name,
            "date": row["date_utc"],
            "is_from_me": bool(row["is_from_me"]),
        })

    return messages


def extract_spotify_links(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract all Spotify URLs from a chat within a date range.

    Args:
        chat_id: The chat ROWID
        start_date: ISO date string (defaults to 30 days ago)
        end_date: ISO date string (defaults to now)

    Returns dict with: links (list of spotify URLs), count, date_range
    """
    db_path = get_db_path()

    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now().isoformat()
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).isoformat()

    # Query messages with Spotify links
    df = query_spotify_messages(db_path, [chat_id], start_date, end_date)

    if df.empty:
        return {
            "links": [],
            "count": 0,
            "date_range": {"start": start_date, "end": end_date},
        }

    # Extract URLs from final_text column
    all_urls = []
    for text in df["final_text"].dropna():
        urls = extract_spotify_urls(str(text))
        all_urls.extend(urls)

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for url in all_urls:
        # Normalize URL (remove query params for dedup)
        normalized = url.split("?")[0]
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(url)

    return {
        "links": unique_urls,
        "count": len(unique_urls),
        "date_range": {"start": start_date, "end": end_date},
    }


def get_chat_stats(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get statistics about Spotify link sharing in a chat.

    Returns: total_messages, spotify_messages, top_sharers, unique_tracks
    """
    db_path = get_db_path()

    # Default date range: last 30 days
    if not end_date:
        end_date = datetime.now().isoformat()
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).isoformat()

    # Get all messages with Spotify links
    df = query_spotify_messages(db_path, [chat_id], start_date, end_date)

    if df.empty:
        return {
            "total_spotify_messages": 0,
            "unique_tracks": 0,
            "top_sharers": [],
            "date_range": {"start": start_date, "end": end_date},
        }

    # Count by sender
    sender_counts = {}
    all_tracks = set()

    for _, row in df.iterrows():
        # Get sender name
        is_from_me = bool(row.get("is_from_me", 0))
        sender = "You" if is_from_me else (row.get("contact_info") or "Unknown")

        # Extract URLs
        text = str(row.get("final_text", "") or row.get("text", ""))
        urls = extract_spotify_urls(text)

        for url in urls:
            # Count per sender
            sender_counts[sender] = sender_counts.get(sender, 0) + 1

            # Extract track ID for unique count
            match = re.search(r"spotify\.com/track/([a-zA-Z0-9]+)", url)
            if match:
                all_tracks.add(match.group(1))

    # Sort sharers by count
    top_sharers = [
        {"name": name, "count": count}
        for name, count in sorted(sender_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "total_spotify_messages": len(df),
        "unique_tracks": len(all_tracks),
        "top_sharers": top_sharers[:10],
        "date_range": {"start": start_date, "end": end_date},
    }


def find_chats_with_spotify(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Find chats that contain Spotify links, ordered by link count.

    Returns list of chats with their Spotify link counts.
    """
    import pandas as pd

    db_path = get_db_path()

    # Get messages with Spotify links from the last 6 months
    end_date = datetime.now().isoformat()
    start_date = (datetime.now() - timedelta(days=180)).isoformat()

    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)

    # Query to find chats with Spotify links
    query = """
        SELECT
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            COUNT(DISTINCT message.ROWID) as spotify_message_count
        FROM chat
        JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE message.date BETWEEN ? AND ?
        AND (
            message.text LIKE '%spotify.com%'
            OR message.text LIKE '%spotify.link%'
        )
        GROUP BY chat.ROWID
        HAVING spotify_message_count > 0
        ORDER BY spotify_message_count DESC
        LIMIT ?
    """

    with db_connection(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=[start_ts, end_ts, limit])

    if df.empty:
        return []

    result = []
    for _, row in df.iterrows():
        name = row["display_name"] or row["chat_identifier"] or "Unknown"
        result.append({
            "chat_id": int(row["chat_id"]),
            "name": name,
            "spotify_link_count": int(row["spotify_message_count"]),
        })

    return result
