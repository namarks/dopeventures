"""
Optimized SQL queries for on-demand data extraction from chat.db.
These queries filter at the database level instead of processing everything upfront.
Many helpers accept an optional prepared_db_path to reuse the prepared store
instead of reparsing attributedBody on every call.
"""

from .message_queries import (
    get_user_db_path,
    get_recent_messages_for_chat,
    get_chat_list,
    query_messages_with_urls,
    query_spotify_messages,
    query_all_messages_for_stats,
)
from .search import (
    search_chats_by_name,
    advanced_chat_search,
    advanced_chat_search_streaming,
)
from .time_utils import convert_to_apple_timestamp
from .url_utils import extract_spotify_urls, extract_all_urls

__all__ = [
    "get_user_db_path",
    "get_recent_messages_for_chat",
    "get_chat_list",
    "query_messages_with_urls",
    "query_spotify_messages",
    "query_all_messages_for_stats",
    "search_chats_by_name",
    "advanced_chat_search",
    "advanced_chat_search_streaming",
    "convert_to_apple_timestamp",
    "extract_spotify_urls",
    "extract_all_urls",
]
