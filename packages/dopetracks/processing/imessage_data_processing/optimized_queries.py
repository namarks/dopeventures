"""
Optimized SQL queries for on-demand data extraction from chat.db.
These queries filter at the database level instead of processing everything upfront.
"""
import os
import sqlite3
import pandas as pd
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Apple timestamp epoch (January 1, 2001)
APPLE_EPOCH = datetime(2001, 1, 1)

def convert_to_apple_timestamp(date_str: str) -> int:
    """Convert ISO date string to Apple timestamp (nanoseconds since 2001-01-01)."""
    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        # Assume local time if no timezone
        dt = dt.replace(tzinfo=None)
    delta = dt - APPLE_EPOCH
    return int(delta.total_seconds() * 1e9)

def get_user_db_path(user_data_service) -> Optional[str]:
    """Get the Messages database path for a user."""
    # Try preferred path first
    preferred_path = user_data_service.get_preferred_db_path()
    if preferred_path and os.path.exists(preferred_path):
        return preferred_path
    
    # Check uploaded files
    uploaded_files = user_data_service.get_uploaded_files()
    for file in uploaded_files:
        if file.original_filename.endswith('.db') and os.path.exists(file.storage_path):
            return file.storage_path
    
    # Try system paths
    system_user = os.path.expanduser("~").split("/")[-1]
    possible_paths = [
        f"/Users/{system_user}/Library/Messages/chat.db",
        f"/Users/{user_data_service.user.username}/Library/Messages/chat.db",
        os.path.expanduser("~/Library/Messages/chat.db")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                # Test database access
                conn = sqlite3.connect(path)
                conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
                conn.close()
                return path
            except Exception:
                continue
    
    return None

def get_recent_messages_for_chat(db_path: str, chat_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent messages from a chat to help user identify which chat entry to use.
    Returns preview of most recent messages.
    
    Parses attributedBody for complete message text (not just text field).
    """
    from . import data_enrichment as de
    
    conn = sqlite3.connect(db_path)
    
    # Get messages with both text and attributedBody, including handle info for sender names
    query = """
        SELECT 
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
        ORDER BY message.date DESC
        LIMIT ?
    """
    
    df = pd.read_sql_query(query, conn, params=[chat_id, limit])
    conn.close()
    
    # Parse attributedBody for messages that have it
    df['extracted_text'] = df['attributedBody'].apply(de.parse_AttributeBody)
    
    # Create final_text (text field OR extracted from attributedBody)
    df['final_text'] = df.apply(
        lambda row: row['text'] if pd.notna(row['text']) and row['text'] != ''
        else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict) 
        else None,
        axis=1
    )
    
    messages = []
    for _, row in df.iterrows():
        text = row['final_text']
        if not text:  # Skip if no text found
            continue
        
        # Get sender name/contact info
        sender_name = None
        if bool(row['is_from_me']):
            sender_name = "You"
        else:
            # Use handle.id (phone number or email) as sender identifier
            sender_name = row['sender_contact'] if pd.notna(row['sender_contact']) else "Unknown"
        
        # Don't truncate - let frontend handle display formatting
        # Frontend will show preview with proper styling
        messages.append({
            "text": text,
            "is_from_me": bool(row['is_from_me']),
            "sender_name": sender_name,
            "date": row['date_utc']
        })
    
    return messages

def get_chat_list(db_path: str) -> List[Dict[str, Any]]:
    """
    Get list of all chats with basic statistics.
    Fast query - no message processing needed.
    """
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            COUNT(DISTINCT message.ROWID) as message_count,
            COUNT(DISTINCT message.handle_id) as member_count,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.display_name IS NOT NULL
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier
        HAVING message_count > 0
        ORDER BY message_count DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Don't deduplicate - show all chat entries so user can choose
    # Group by chat_identifier to identify potential duplicates
    df = df.sort_values('message_count', ascending=False)
    
    results = []
    for _, row in df.iterrows():
        # Get recent messages for this chat (available in details view)
        recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)
        
        results.append({
            "chat_id": int(row['chat_id']),
            "name": row['display_name'] or row['chat_identifier'],
            "chat_identifier": row['chat_identifier'],
            "members": int(row['member_count']) if pd.notna(row['member_count']) else 0,
            "total_messages": int(row['message_count']),
            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
            "last_message_date": row['last_message_date'],
            "recent_messages": recent_messages  # Available but not shown in main table - shown in details view
        })
    
    return results

def extract_spotify_urls(text: str) -> List[str]:
    """Extract Spotify URLs from text using regex."""
    if not text:
        return []
    # Match both open.spotify.com and spotify.link URLs
    pattern = r'https?://(open\.spotify\.com|spotify\.link)/[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(pattern, text)
    # Reconstruct full URLs (re.findall returns tuples for groups)
    full_urls = []
    for match in re.finditer(pattern, text):
        full_urls.append(match.group(0))
    return full_urls

def extract_all_urls(text: str) -> List[Dict[str, str]]:
    """
    Extract all URLs from text and categorize them by type.
    Returns a list of dicts with 'url' and 'type' keys.
    """
    if not text:
        return []
    
    from urllib.parse import urlparse
    
    # More comprehensive URL pattern that handles:
    # - Standard URLs
    # - URLs with query parameters (?key=value)
    # - URLs with fragments (#section)
    # - URLs ending with punctuation (which we'll strip)
    # This pattern matches URLs until whitespace or common punctuation that typically ends a sentence
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    matches = list(re.finditer(url_pattern, text))
    
    categorized_urls = []
    for match in matches:
        url = match.group(0)
        # Strip trailing punctuation that might have been captured (but keep it if it's part of the URL)
        # Only strip if it's clearly sentence-ending punctuation
        url = url.rstrip('.,;!?)')
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Helper function to check if domain matches (handles subdomains and avoids false positives)
            def domain_matches(domain, pattern):
                """Check if domain matches pattern, handling subdomains correctly."""
                # Remove 'www.' prefix if present
                domain_clean = domain.replace('www.', '')
                pattern_clean = pattern.replace('www.', '')
                
                # Check exact match or subdomain match (e.g., 'api.spotify.com' matches 'spotify.com')
                return (domain_clean == pattern_clean or 
                        domain_clean.endswith('.' + pattern_clean))
            
            # Categorize by domain (using precise matching to avoid false positives like 'dopdx.com' matching 'x.com')
            url_type = "other"
            if domain_matches(domain, 'spotify.com') or domain_matches(domain, 'spotify.link'):
                url_type = "spotify"
            elif domain_matches(domain, 'youtube.com') or domain_matches(domain, 'youtu.be'):
                url_type = "youtube"
            elif domain_matches(domain, 'instagram.com') or domain_matches(domain, 'instagr.am'):
                url_type = "instagram"
            elif domain_matches(domain, 'music.apple.com') or domain_matches(domain, 'itunes.apple.com'):
                url_type = "apple_music"
            elif domain_matches(domain, 'tiktok.com'):
                url_type = "tiktok"
            elif domain_matches(domain, 'twitter.com') or domain_matches(domain, 'x.com'):
                url_type = "twitter"
            elif domain_matches(domain, 'facebook.com') or domain_matches(domain, 'fb.com'):
                url_type = "facebook"
            elif domain_matches(domain, 'soundcloud.com'):
                url_type = "soundcloud"
            elif domain_matches(domain, 'bandcamp.com'):
                url_type = "bandcamp"
            elif domain_matches(domain, 'tidal.com'):
                url_type = "tidal"
            elif domain_matches(domain, 'amazon.com') and ('music' in domain or '/music' in parsed.path):
                url_type = "amazon_music"
            elif domain_matches(domain, 'deezer.com'):
                url_type = "deezer"
            elif domain_matches(domain, 'pandora.com'):
                url_type = "pandora"
            elif domain_matches(domain, 'iheart.com'):
                url_type = "iheart"
            elif domain_matches(domain, 'tunein.com'):
                url_type = "tunein"
            
            categorized_urls.append({
                "url": url,
                "type": url_type
            })
        except Exception as e:
            # If URL parsing fails, still add it as "other" type
            logger.warning(f"Failed to parse URL: {url} - {e}")
            categorized_urls.append({
                "url": url,
                "type": "other"
            })
    
    return categorized_urls

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
    from . import data_enrichment as de
    
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    conn = sqlite3.connect(db_path)
    
    placeholders = ','.join(['?'] * len(chat_ids))
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
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return df
    
    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if 'associated_message_type' in df.columns:
        df = df[df['associated_message_type'].isna() | (df['associated_message_type'] == 0)].copy()
    
    # Parse attributedBody for messages that have it
    # This extracts text from the binary field
    df['extracted_text'] = df['attributedBody'].apply(de.parse_AttributeBody)
    
    # Create final_text column (text field OR extracted from attributedBody)
    df['final_text'] = df.apply(
        lambda row: row['text'] if pd.notna(row['text']) and row['text'] != ''
        else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict) 
        else None,
        axis=1
    )
    
    # Filter to only messages with ANY URLs (http or https)
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    df['has_url'] = df['final_text'].astype(str).str.contains(url_pattern, case=False, na=False, regex=True)
    
    # Return only messages with URLs
    df_filtered = df[df['has_url']].copy()
    
    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=['extracted_text', 'has_url'])
    
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
    from . import data_enrichment as de
    
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    conn = sqlite3.connect(db_path)
    
    placeholders = ','.join(['?'] * len(chat_ids))
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
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return df
    
    # Filter out reactions before processing (reactions don't have meaningful text)
    # associated_message_type is NULL or 0 for regular messages, non-zero for reactions
    if 'associated_message_type' in df.columns:
        df = df[df['associated_message_type'].isna() | (df['associated_message_type'] == 0)].copy()
    
    # Parse attributedBody for messages that have it
    # This extracts text from the binary field
    df['extracted_text'] = df['attributedBody'].apply(de.parse_AttributeBody)
    
    # Create final_text column (text field OR extracted from attributedBody)
    df['final_text'] = df.apply(
        lambda row: row['text'] if pd.notna(row['text']) and row['text'] != ''
        else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict) 
        else None,
        axis=1
    )
    
    # Now filter to only messages with Spotify links in final_text
    spotify_pattern = r'https?://(open\.spotify\.com|spotify\.link)/[^\s<>"{}|\\^`\[\]]+'
    df['has_spotify'] = df['final_text'].astype(str).str.contains(spotify_pattern, case=False, na=False, regex=True)
    
    # Return only messages with Spotify links
    df_filtered = df[df['has_spotify']].copy()
    
    # Clean up temporary columns
    df_filtered = df_filtered.drop(columns=['extracted_text', 'has_spotify'])
    
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
    start_ts = convert_to_apple_timestamp(start_date)
    end_ts = convert_to_apple_timestamp(end_date)
    
    conn = sqlite3.connect(db_path)
    
    placeholders = ','.join(['?'] * len(chat_ids))
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
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df

def search_chats_by_name(db_path: str, query: str) -> List[Dict[str, Any]]:
    """
    Search chats by name, identifier, or member names.
    Fast query for chat search functionality.
    
    Searches across:
    - Chat display name
    - Chat identifier (phone numbers, email addresses)
    - Member names (via handle table)
    """
    conn = sqlite3.connect(db_path)
    
    # Search pattern for SQL LIKE
    search_pattern = f'%{query}%'
    
    # First, find handle IDs that match the search query (member names)
    handle_query = """
        SELECT DISTINCT handle.ROWID as handle_id
        FROM handle
        WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
    """
    handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
    handle_ids = handle_matches['handle_id'].tolist() if not handle_matches.empty else []
    
    # Build the main search query
    # Search in: chat.display_name, chat.chat_identifier, and member handles
    if handle_ids:
        # If we found matching handles, include them in the search
        handle_placeholders = ','.join(['?'] * len(handle_ids))
        # Use a subquery to find chats that match any criteria
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
        # No matching handles, just search chat name and identifier
        search_query = """
            SELECT DISTINCT chat.ROWID as chat_id
            FROM chat
            WHERE (
                chat.display_name LIKE ?
                OR chat.chat_identifier LIKE ?
            )
        """
        params = [search_pattern, search_pattern]
    
    # Get matching chat IDs first
    matching_chats = pd.read_sql_query(search_query, conn, params=params)
    
    if matching_chats.empty:
        conn.close()
        return []
    
    chat_ids = matching_chats['chat_id'].tolist()
    chat_id_placeholders = ','.join(['?'] * len(chat_ids))
    
    # Now get full statistics for matching chats
    stats_query = f"""
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            COUNT(DISTINCT message.ROWID) as message_count,
            COUNT(DISTINCT message.handle_id) as member_count,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.ROWID IN ({chat_id_placeholders})
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier
        HAVING message_count > 0
        ORDER BY message_count DESC
        LIMIT 50
    """
    
    df = pd.read_sql_query(stats_query, conn, params=chat_ids)
    conn.close()
    
    # Don't deduplicate - show all matches so user can choose which chat entry to use
    df = df.sort_values('message_count', ascending=False)
    
    results = []
    for _, row in df.iterrows():
        # Get recent messages to help user identify which chat entry this is
        # This parses attributedBody for display purposes (to help user pick the right chat)
        recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)
        
        results.append({
            "chat_id": int(row['chat_id']),
            "name": row['display_name'] or row['chat_identifier'],
            "chat_identifier": row['chat_identifier'],
            "members": int(row['member_count']) if pd.notna(row['member_count']) else 0,
            "total_messages": int(row['message_count']),
            "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
            "last_message_date": row['last_message_date'],
            "recent_messages": recent_messages  # Available but not shown in main table - shown in details view
            # Note: Spotify link counts are NOT included here - they require parsing attributedBody
            # Spotify links are only extracted when chats are selected for playlist creation
        })
    
    return results
