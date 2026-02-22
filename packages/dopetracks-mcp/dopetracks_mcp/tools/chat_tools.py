"""
MCP tools for iMessage chat operations.

Tools: search_chats, get_messages, get_chat_stats
"""

from typing import Any, Dict, List, Optional

from ..core import imessage


def search_chats(
    query: Optional[str] = None,
    with_spotify_links: bool = False,
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search for chats by name or find chats with Spotify links.

    Args:
        query: Search term for chat name, identifier, or participant name.
               If empty/None, lists all chats.
        with_spotify_links: If True, only return chats that contain Spotify links
        limit: Maximum number of results (default 20)

    Returns:
        Dictionary with 'chats' list and 'count'

    Example:
        search_chats(query="dopetracks") -> chats matching "dopetracks"
        search_chats(with_spotify_links=True) -> chats with Spotify links
    """
    try:
        if with_spotify_links:
            chats = imessage.find_chats_with_spotify(limit=limit)
            return {
                "chats": chats,
                "count": len(chats),
                "filter": "with_spotify_links",
            }

        if query:
            chats = imessage.search_chats(query, limit=limit)
        else:
            chats = imessage.list_chats(limit=limit)

        return {
            "chats": chats,
            "count": len(chats),
            "query": query,
        }

    except Exception as e:
        return {
            "error": str(e),
            "chats": [],
            "count": 0,
        }


def get_messages(
    chat_id: int,
    limit: int = 50,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    sender: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get messages from a specific chat.

    Args:
        chat_id: The chat ID (from search_chats results)
        limit: Maximum messages to return (default 50)
        start_date: Start of date range (ISO format, e.g., "2024-01-01")
        end_date: End of date range (ISO format, e.g., "2024-12-31")
        search: Filter messages containing this text
        sender: Filter messages by sender name (case-insensitive partial match)

    Returns:
        Dictionary with 'messages' list and metadata

    Example:
        get_messages(chat_id=123, start_date="2024-12-01", end_date="2024-12-31")
        get_messages(chat_id=123, sender="Chet")
    """
    try:
        messages = imessage.get_messages(
            chat_id=chat_id,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            search=search,
            sender=sender,
        )

        return {
            "messages": messages,
            "count": len(messages),
            "chat_id": chat_id,
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "search": search,
                "sender": sender,
            },
        }

    except Exception as e:
        return {
            "error": str(e),
            "messages": [],
            "count": 0,
            "chat_id": chat_id,
        }


def extract_spotify_links(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract all Spotify URLs from a chat.

    Args:
        chat_id: The chat ID (from search_chats results)
        start_date: Start of date range (ISO format). Defaults to 30 days ago.
        end_date: End of date range (ISO format). Defaults to now.

    Returns:
        Dictionary with 'links' (list of Spotify URLs), 'count', and 'date_range'

    Example:
        extract_spotify_links(chat_id=123, start_date="2024-12-01")
    """
    try:
        result = imessage.extract_spotify_links(
            chat_id=chat_id,
            start_date=start_date,
            end_date=end_date,
        )
        result["chat_id"] = chat_id
        return result

    except Exception as e:
        return {
            "error": str(e),
            "links": [],
            "count": 0,
            "chat_id": chat_id,
        }


def get_chat_stats(
    chat_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get statistics about Spotify link sharing in a chat.

    Args:
        chat_id: The chat ID (from search_chats results)
        start_date: Start of date range (ISO format). Defaults to 30 days ago.
        end_date: End of date range (ISO format). Defaults to now.

    Returns:
        Dictionary with statistics:
        - total_spotify_messages: Number of messages with Spotify links
        - unique_tracks: Number of unique tracks shared
        - top_sharers: List of {name, count} for top contributors
        - date_range: The date range analyzed

    Example:
        get_chat_stats(chat_id=123, start_date="2024-01-01", end_date="2024-12-31")
    """
    try:
        result = imessage.get_chat_stats(
            chat_id=chat_id,
            start_date=start_date,
            end_date=end_date,
        )
        result["chat_id"] = chat_id
        return result

    except Exception as e:
        return {
            "error": str(e),
            "total_spotify_messages": 0,
            "unique_tracks": 0,
            "top_sharers": [],
            "chat_id": chat_id,
        }
