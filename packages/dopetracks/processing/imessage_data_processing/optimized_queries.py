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
            conn = sqlite3.connect(default_path)
            conn.execute("SELECT COUNT(*) FROM message LIMIT 1;")
            conn.close()
            return default_path
        except Exception as e:
            logger.warning(f"Messages database exists but cannot be accessed: {e}")
            return None
    
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
    # Import contact info function
    try:
        try:
            from ..contacts_data_processing.import_contact_info import get_contact_info_by_handle
        except ImportError:
            logger.debug("Could not import contact info function: contacts_data_processing module not available")
            get_contact_info_by_handle = None
        use_contact_info = True
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
            -- Participant count: distinct handles + self if present
            (
              COUNT(DISTINCT message.handle_id)
              + CASE WHEN SUM(CASE WHEN message.is_from_me = 1 THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END
            ) AS member_count,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.display_name IS NOT NULL
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier
        HAVING message_count > 0
        ORDER BY last_message_date DESC
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
    - Member phone numbers/emails (via handle table)
    - Member contact names (via Contacts database)
    """
    conn = sqlite3.connect(db_path)
    
    # Search pattern for SQL LIKE
    search_pattern = f'%{query}%'
    
    # First, find handle IDs that match the search query (phone numbers/emails)
    handle_query = """
        SELECT DISTINCT handle.ROWID as handle_id
        FROM handle
        WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
    """
    handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
    handle_ids = handle_matches['handle_id'].tolist() if not handle_matches.empty else []
    
    # Also search Contacts database for contact names, then find matching handles
    try:
        from ..contacts_data_processing.import_contact_info import get_contacts_db_path, clean_phone_number
        
        contacts_db_path = get_contacts_db_path()
        contacts_conn = sqlite3.connect(contacts_db_path)
        
        # Search for contacts by name
        contact_name_query = """
            SELECT DISTINCT
                ZABCDRECORD.ZFIRSTNAME as first_name,
                ZABCDRECORD.ZLASTNAME as last_name,
                ZABCDPHONENUMBER.ZFULLNUMBER as phone_number,
                ZABCDEMAILADDRESS.ZADDRESS as email
            FROM ZABCDRECORD
            LEFT JOIN ZABCDPHONENUMBER ON ZABCDRECORD.Z_PK = ZABCDPHONENUMBER.ZOWNER
            LEFT JOIN ZABCDEMAILADDRESS ON ZABCDRECORD.Z_PK = ZABCDEMAILADDRESS.ZOWNER
            WHERE (
                (ZABCDRECORD.ZFIRSTNAME IS NOT NULL AND ZABCDRECORD.ZFIRSTNAME LIKE ?)
                OR (ZABCDRECORD.ZLASTNAME IS NOT NULL AND ZABCDRECORD.ZLASTNAME LIKE ?)
                OR (ZABCDRECORD.ZFIRSTNAME || ' ' || ZABCDRECORD.ZLASTNAME LIKE ?)
            )
        """
        contact_matches = pd.read_sql_query(
            contact_name_query, 
            contacts_conn, 
            params=[search_pattern, search_pattern, search_pattern]
        )
        contacts_conn.close()
        
        # Get phone numbers and emails from matching contacts
        contact_phones = []
        contact_emails = []
        for _, row in contact_matches.iterrows():
            if pd.notna(row['phone_number']):
                # Clean phone number for matching
                cleaned_phone = clean_phone_number(str(row['phone_number']))
                if cleaned_phone:
                    contact_phones.append(cleaned_phone)
            if pd.notna(row['email']):
                contact_emails.append(str(row['email']).lower())
        
        # Find handles in Messages database that match these contact phone numbers/emails
        if contact_phones or contact_emails:
            handle_search_conditions = []
            handle_search_params = []
            
            # Search for handles matching contact phone numbers
            for phone in contact_phones:
                # Try different phone number formats
                handle_search_conditions.append("(handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?)")
                handle_search_params.extend([f'%{phone}%', f'%{phone}%'])
            
            # Search for handles matching contact emails
            for email in contact_emails:
                handle_search_conditions.append("(LOWER(handle.id) = ? OR LOWER(handle.uncanonicalized_id) = ?)")
                handle_search_params.extend([email, email])
            
            if handle_search_conditions:
                contact_handle_query = f"""
                    SELECT DISTINCT handle.ROWID as handle_id
                    FROM handle
                    WHERE {' OR '.join(handle_search_conditions)}
                """
                contact_handle_matches = pd.read_sql_query(
                    contact_handle_query, 
                    conn, 
                    params=handle_search_params
                )
                contact_handle_ids = contact_handle_matches['handle_id'].tolist() if not contact_handle_matches.empty else []
                # Add to existing handle_ids (avoid duplicates)
                handle_ids = list(set(handle_ids + contact_handle_ids))
        
    except Exception as e:
        # If Contacts database access fails, just continue with phone/email search
        logger.debug(f"Could not search Contacts database: {e}")
        pass
    
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

def advanced_chat_search(
    db_path: str,
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[List[str]] = None,
    message_content: Optional[str] = None,
    limit_to_recent: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Advanced chat search with multiple filter criteria:
    - Text query (chat name, identifier, or participant)
    - Date range (messages within this range)
    - Participants (people in the chat)
    - Message content (specific words in messages)
    
    Returns chats that match ALL specified criteria.
    """
    from . import data_enrichment as de
    
    logger.info(f"advanced_chat_search called: query={query}, start_date={start_date}, end_date={end_date}, message_content={message_content}")
    conn = sqlite3.connect(db_path)
    
    # Build WHERE conditions dynamically
    conditions = []
    params = []
    
    # Step 1: Find handle IDs for participant search
    participant_handle_ids = []
    if participant_names:
        for name in participant_names:
            # Search in handle table
            handle_query = """
                SELECT DISTINCT handle.ROWID as handle_id
                FROM handle
                WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
            """
            search_pattern = f'%{name}%'
            handle_matches = pd.read_sql_query(handle_query, conn, params=[search_pattern, search_pattern])
            if not handle_matches.empty:
                participant_handle_ids.extend(handle_matches['handle_id'].tolist())
            
            # Also search Contacts database
            try:
                from ..contacts_data_processing.import_contact_info import get_contacts_db_path, clean_phone_number
                contacts_db_path = get_contacts_db_path()
                if contacts_db_path and os.path.exists(contacts_db_path):
                    contacts_conn = sqlite3.connect(contacts_db_path)
                    contact_name_query = """
                        SELECT DISTINCT
                            ZABCDPHONENUMBER.ZFULLNUMBER as phone_number,
                            ZABCDEMAILADDRESS.ZADDRESS as email
                        FROM ZABCDRECORD
                        LEFT JOIN ZABCDPHONENUMBER ON ZABCDRECORD.Z_PK = ZABCDPHONENUMBER.ZOWNER
                        LEFT JOIN ZABCDEMAILADDRESS ON ZABCDRECORD.Z_PK = ZABCDEMAILADDRESS.ZOWNER
                        WHERE (
                            (ZABCDRECORD.ZFIRSTNAME IS NOT NULL AND ZABCDRECORD.ZFIRSTNAME LIKE ?)
                            OR (ZABCDRECORD.ZLASTNAME IS NOT NULL AND ZABCDRECORD.ZLASTNAME LIKE ?)
                            OR (ZABCDRECORD.ZFIRSTNAME || ' ' || ZABCDRECORD.ZLASTNAME LIKE ?)
                        )
                    """
                    contact_matches = pd.read_sql_query(
                        contact_name_query,
                        contacts_conn,
                        params=[search_pattern, search_pattern, search_pattern]
                    )
                    contacts_conn.close()
                    
                    # Find handles matching these contacts
                    for _, row in contact_matches.iterrows():
                        if pd.notna(row['phone_number']):
                            cleaned_phone = clean_phone_number(str(row['phone_number']))
                            if cleaned_phone:
                                handle_search = """
                                    SELECT DISTINCT handle.ROWID as handle_id
                                    FROM handle
                                    WHERE handle.id LIKE ? OR handle.uncanonicalized_id LIKE ?
                                """
                                handle_matches = pd.read_sql_query(
                                    handle_search,
                                    conn,
                                    params=[f'%{cleaned_phone}%', f'%{cleaned_phone}%']
                                )
                                if not handle_matches.empty:
                                    participant_handle_ids.extend(handle_matches['handle_id'].tolist())
                        if pd.notna(row['email']):
                            email = str(row['email']).lower()
                            handle_search = """
                                SELECT DISTINCT handle.ROWID as handle_id
                                FROM handle
                                WHERE LOWER(handle.id) = ? OR LOWER(handle.uncanonicalized_id) = ?
                            """
                            handle_matches = pd.read_sql_query(
                                handle_search,
                                conn,
                                params=[email, email]
                            )
                            if not handle_matches.empty:
                                participant_handle_ids.extend(handle_matches['handle_id'].tolist())
            except Exception as e:
                logger.debug(f"Could not search Contacts database: {e}")
        
        participant_handle_ids = list(set(participant_handle_ids))  # Remove duplicates
    
    # Step 2: Build query to find matching chat IDs based on message criteria
    # NOTE: If only message_content is provided (no date/participant filters), we skip text filtering here
    # and check attributedBody for all chats in Step 4. This is because many messages only have content
    # in attributedBody, not in the text field.
    message_conditions = []
    message_params = []
    
    # Date range filter
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
    
    # Participant filter
    if participant_handle_ids:
        handle_placeholders = ','.join(['?'] * len(participant_handle_ids))
        message_conditions.append(f"message.handle_id IN ({handle_placeholders})")
        message_params.extend(participant_handle_ids)
    
    # Message content filter (for text field) - DON'T use this when message_content is provided
    # because many messages only have content in attributedBody, not in the text field.
    # We'll check both text and attributedBody in Step 4 instead.
    # Only filter by text if we have NO other way to filter (which shouldn't happen with message_content)
    # Actually, never filter by text when message_content is provided - always check attributedBody in Step 4
    
    # Find chat IDs that have messages matching the criteria
    # If message_content is provided, we need to check attributedBody in Step 4,
    # so we should get all chats (or chats matching date/participant filters) without filtering by text
    if message_content and not (start_date or end_date or participant_handle_ids):
        # Only message_content filter - get all chats, will filter by content in Step 4
        chat_ids_query = "SELECT DISTINCT chat.ROWID as chat_id FROM chat"
        matching_chats = pd.read_sql_query(chat_ids_query, conn)
        chat_ids = matching_chats['chat_id'].tolist() if not matching_chats.empty else []
        logger.info(f"Step 2: Got {len(chat_ids)} chats (message_content only, will check attributedBody in Step 4)")
    elif message_conditions:
        # We have date/participant filters
        # If message_content is also provided, we'll check it in Step 4 (attributedBody), not here
        # Base condition: message must have text or attributedBody
        message_conditions.append("(message.text IS NOT NULL OR message.attributedBody IS NOT NULL)")
        message_conditions.append("(message.associated_message_type IS NULL OR message.associated_message_type = 0)")
        
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
            logger.warning(f"Step 2: No chats found matching date/participant filters")
            conn.close()
            return []
        
        chat_ids = matching_chats['chat_id'].tolist()
        logger.info(f"Step 2: Found {len(chat_ids)} chats matching message criteria (date/participant filters, message_content will be checked in Step 4)")
    else:
        # No message filters - get all chats
        chat_ids_query = "SELECT DISTINCT chat.ROWID as chat_id FROM chat"
        matching_chats = pd.read_sql_query(chat_ids_query, conn)
        chat_ids = matching_chats['chat_id'].tolist() if not matching_chats.empty else []
        logger.info(f"Step 2: No message filters, got {len(chat_ids)} total chats")
    
    # Step 3: Limit to most recent chats if specified
    if limit_to_recent is not None and chat_ids and len(chat_ids) > limit_to_recent:
        # Get most recent chats by last_message_date
        chat_id_placeholders = ','.join(['?'] * len(chat_ids))
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
        logger.info(f"Limited to {len(chat_ids)} most recent chats (from {len(chat_ids)} total)")
    
    # Step 4: If message_content was specified, we need to check attributedBody too
    # This requires loading messages and parsing attributedBody
    # LIMIT: Only process up to 10,000 messages to prevent timeout
    logger.info(f"Step 4: message_content={message_content}, chat_ids count={len(chat_ids) if chat_ids else 0}")
    if message_content and chat_ids:
        # Check if FTS is available
        use_fts = False
        if FTS_AVAILABLE:
            fts_db_path = get_fts_db_path(db_path)
            use_fts = is_fts_available(fts_db_path)
        
        if use_fts:
            logger.info(f"Using FTS for message content search")
            # Use FTS search - much faster!
            end_ts = None
            if end_date:
                end_ts = convert_to_apple_timestamp(end_date)
            
            matching_messages = search_fts(
                fts_db_path=fts_db_path,
                search_term=message_content,
                chat_ids=chat_ids,
                start_date=start_date,
                end_date=end_ts,
                limit=10000
            )
            
            if not matching_messages.empty:
                valid_chat_ids_set = set(matching_messages['chat_id'].unique().tolist())
                chat_ids = [cid for cid in chat_ids if cid in valid_chat_ids_set]
            else:
                chat_ids = []
        else:
            # Fall back to original method (parsing attributedBody)
            logger.info(f"FTS not available, using fallback method")
            MAX_MESSAGES_TO_PROCESS = 10000
            
            # Get messages from matching chats to check attributedBody
            chat_id_placeholders = ','.join(['?'] * len(chat_ids))
            message_check_query = f"""
                SELECT 
                    chat.ROWID as chat_id,
                    message.text,
                    message.attributedBody,
                    message.date
                FROM chat
                JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                JOIN message ON chat_message_join.message_id = message.ROWID
                WHERE chat.ROWID IN ({chat_id_placeholders})
                AND (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
                AND (message.associated_message_type IS NULL OR message.associated_message_type = 0)
            """
            
            # Add date range if specified - IMPORTANT: when checking message_content with date range,
            # we need to check messages WITHIN the date range that contain the content
            # Parameters must be in order: chat_ids first (for IN clause), then date params
            message_params_check = list(chat_ids)
            if start_date or end_date:
                if start_date and end_date:
                    start_ts = convert_to_apple_timestamp(start_date)
                    end_ts = convert_to_apple_timestamp(end_date)
                    message_check_query += " AND message.date BETWEEN ? AND ?"
                    message_params_check.extend([start_ts, end_ts])  # Add dates after chat_ids
                elif start_date:
                    start_ts = convert_to_apple_timestamp(start_date)
                    message_check_query += " AND message.date >= ?"
                    message_params_check.append(start_ts)
                else:
                    end_ts = convert_to_apple_timestamp(end_date)
                    message_check_query += " AND message.date <= ?"
                    message_params_check.append(end_ts)
            
            # Increase limit if we have date range (to ensure we check enough messages)
            if start_date or end_date:
                MAX_MESSAGES_TO_PROCESS = 50000  # More messages when date range is specified
            
            # Add LIMIT to prevent processing too many messages
            # When checking message content, we need to check enough messages to find matches
            message_check_query += f" LIMIT {MAX_MESSAGES_TO_PROCESS}"
            
            messages_df = pd.read_sql_query(message_check_query, conn, params=message_params_check)
            
            logger.info(f"Step 4: Checking {len(messages_df)} messages for content '{message_content}' in {len(chat_ids)} chats (date range: {start_date} to {end_date})")
            
            if messages_df.empty:
                logger.warning(f"Step 4: No messages found in date range for {len(chat_ids)} chats. This might mean messages with '{message_content}' are outside the date range.")
                # Don't return empty - maybe messages with content are outside date range but we should still check
                # Actually, if no messages in date range, we can't find content in date range, so return empty
                conn.close()
                return []
            
            if not messages_df.empty:
                # Parse attributedBody (this is the expensive operation)
                # Process in chunks to avoid memory issues
                chunk_size = 1000
                valid_chat_ids_set = set()
                
                for i in range(0, len(messages_df), chunk_size):
                    chunk = messages_df.iloc[i:i+chunk_size].copy()
                    
                    # Parse attributedBody for this chunk
                    chunk['extracted_text'] = chunk['attributedBody'].apply(de.parse_AttributeBody)
                    chunk['final_text'] = chunk.apply(
                        lambda row: row['text'] if pd.notna(row['text']) and row['text'] != ''
                        else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict)
                        else None,
                        axis=1
                    )
                    
                    # Filter by message content
                    matching_chunk = chunk[
                        chunk['final_text'].astype(str).str.contains(message_content, case=False, na=False)
                    ]
                    
                    # Collect chat IDs that have matching messages
                    if not matching_chunk.empty:
                        valid_chat_ids_set.update(matching_chunk['chat_id'].unique().tolist())
                
                # Filter chat_ids to only those with matching messages
                if valid_chat_ids_set:
                    chat_ids = [cid for cid in chat_ids if cid in valid_chat_ids_set]
                else:
                    # No messages found with the content in the specified date range
                    chat_ids = []
        
        if not chat_ids:
            conn.close()
            return []
    
    # Step 4: Apply text query filter (chat name, identifier) if provided
    if query:
        search_pattern = f'%{query}%'
        chat_id_placeholders = ','.join(['?'] * len(chat_ids)) if chat_ids else "NULL"
        
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
            conn.close()
            return []
        
        chat_ids = filtered_chats['chat_id'].tolist()
    
    if not chat_ids:
        conn.close()
        return []
    
    # Step 5: Get full statistics for matching chats (same as search_chats_by_name)
    chat_id_placeholders = ','.join(['?'] * len(chat_ids))
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
        LIMIT 100
    """
    
    df = pd.read_sql_query(stats_query, conn, params=chat_ids)
    conn.close()
    
    results = []
    for _, row in df.iterrows():
        recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)
        
        results.append({
            "chat_id": int(row['chat_id']),
            "name": row['display_name'] or row['chat_identifier'],
            "chat_identifier": row['chat_identifier'],
            "members": int(row['member_count']) if pd.notna(row['member_count']) else 0,
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
    limit_to_recent: Optional[int] = None
):
    """
    Streaming version of advanced_chat_search that yields results as they're found.
    Processes chats in batches and yields results incrementally.
    Limits to most recent chats by default.
    """
    from . import data_enrichment as de
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # Step 1: Find handle IDs for participant search
        participant_handle_ids = []
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
        
        # Step 2: Find initial chat IDs based on message criteria
        message_conditions = []
        message_params = []
        
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
            handle_placeholders = ','.join(['?'] * len(participant_handle_ids))
            message_conditions.append(f"message.handle_id IN ({handle_placeholders})")
            message_params.extend(participant_handle_ids)
        
        # DON'T filter by message.text LIKE when message_content is provided
        # Many messages only have content in attributedBody, not in the text field
        # We'll check both text and attributedBody in Step 5 (batch processing)
        
        message_conditions.append("(message.text IS NOT NULL OR message.attributedBody IS NOT NULL)")
        message_conditions.append("(message.associated_message_type IS NULL OR message.associated_message_type = 0)")
        
        # Get all potential chat IDs first
        # If only message_content is provided (no date/participant filters), get all chats
        if message_content and not (start_date or end_date or participant_handle_ids):
            # Only message_content filter - get all chats, will filter by content in Step 5
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
        
        # Step 3: Limit to most recent chats (if limit specified)
        if limit_to_recent and chat_ids and len(chat_ids) > limit_to_recent:
            chat_id_placeholders = ','.join(['?'] * len(chat_ids))
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
        
        # Step 4: Apply text query filter if provided
        if query and chat_ids:
            search_pattern = f'%{query}%'
            chat_id_placeholders = ','.join(['?'] * len(chat_ids))
            filter_query = f"""
                SELECT DISTINCT chat.ROWID as chat_id
                FROM chat
                WHERE chat.ROWID IN ({chat_id_placeholders})
                AND (chat.display_name LIKE ? OR chat.chat_identifier LIKE ?)
            """
            filtered_chats = pd.read_sql_query(filter_query, conn, params=chat_ids + [search_pattern, search_pattern])
            chat_ids = filtered_chats['chat_id'].tolist() if not filtered_chats.empty else []
        
        if not chat_ids:
            return
        
        # Step 5: Process chats in batches and yield results as they're found
        BATCH_SIZE = 10
        for i in range(0, len(chat_ids), BATCH_SIZE):
            batch_chat_ids = chat_ids[i:i+BATCH_SIZE]
            chat_id_placeholders = ','.join(['?'] * len(batch_chat_ids))
            
            # Get statistics for this batch
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
            """
            
            df = pd.read_sql_query(stats_query, conn, params=batch_chat_ids)
            
            # If message_content is specified, filter this batch
            if message_content and not df.empty:
                # Check if FTS is available
                use_fts = False
                if FTS_AVAILABLE:
                    fts_db_path = get_fts_db_path(db_path)
                    use_fts = is_fts_available(fts_db_path)
                
                if use_fts:
                    # Use FTS search - much faster!
                    end_ts = None
                    if end_date:
                        end_ts = convert_to_apple_timestamp(end_date)
                    
                    matching_messages = search_fts(
                        fts_db_path=fts_db_path,
                        search_term=message_content,
                        chat_ids=batch_chat_ids,
                        start_date=start_date,
                        end_date=end_ts,
                        limit=5000
                    )
                    
                    if not matching_messages.empty:
                        valid_chat_ids_set = set(matching_messages['chat_id'].unique().tolist())
                        df = df[df['chat_id'].isin(valid_chat_ids_set)]
                    else:
                        # No matches in this batch
                        df = pd.DataFrame()
                else:
                    # Fall back to original method (parsing attributedBody)
                    batch_chat_id_placeholders = ','.join(['?'] * len(batch_chat_ids))
                    message_check_query = f"""
                        SELECT 
                            chat.ROWID as chat_id,
                            message.text,
                            message.attributedBody
                        FROM chat
                        JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
                        JOIN message ON chat_message_join.message_id = message.ROWID
                        WHERE chat.ROWID IN ({batch_chat_id_placeholders})
                        AND (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
                        AND (message.associated_message_type IS NULL OR message.associated_message_type = 0)
                    """
                    
                    # Add date range if specified
                    message_params_check = list(batch_chat_ids)
                    if start_date or end_date:
                        if start_date and end_date:
                            start_ts = convert_to_apple_timestamp(start_date)
                            end_ts = convert_to_apple_timestamp(end_date)
                            message_check_query += " AND message.date BETWEEN ? AND ?"
                            message_params_check.extend([start_ts, end_ts])
                        elif start_date:
                            start_ts = convert_to_apple_timestamp(start_date)
                            message_check_query += " AND message.date >= ?"
                            message_params_check.append(start_ts)
                        else:
                            end_ts = convert_to_apple_timestamp(end_date)
                            message_check_query += " AND message.date <= ?"
                            message_params_check.append(end_ts)
                    
                    message_check_query += " LIMIT 5000"
                    
                    messages_df = pd.read_sql_query(message_check_query, conn, params=message_params_check)
                    
                    if not messages_df.empty:
                        # Parse attributedBody in chunks
                        chunk_size = 500
                        valid_chat_ids_set = set()
                        
                        for j in range(0, len(messages_df), chunk_size):
                            try:
                                chunk = messages_df.iloc[j:j+chunk_size].copy()
                                
                                # Parse attributedBody with error handling
                                def safe_parse_attributed_body(attributed_body):
                                    try:
                                        return de.parse_AttributeBody(attributed_body)
                                    except Exception as e:
                                        logger.debug(f"Error parsing attributedBody: {e}")
                                        return {}
                                
                                chunk['extracted_text'] = chunk['attributedBody'].apply(safe_parse_attributed_body)
                                chunk['final_text'] = chunk.apply(
                                    lambda row: row['text'] if pd.notna(row['text']) and row['text'] != ''
                                    else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict)
                                    else None,
                                    axis=1
                                )
                                
                                matching_chunk = chunk[
                                    chunk['final_text'].astype(str).str.contains(message_content, case=False, na=False)
                                ]
                                
                                if not matching_chunk.empty:
                                    valid_chat_ids_set.update(matching_chunk['chat_id'].unique().tolist())
                            except Exception as e:
                                logger.error(f"Error processing message chunk {j}-{j+chunk_size}: {e}", exc_info=True)
                                # Continue with next chunk instead of crashing
                                continue
                        
                        # Filter df to only chats with matching messages
                        if valid_chat_ids_set:
                            df = df[df['chat_id'].isin(valid_chat_ids_set)]
                        else:
                            df = pd.DataFrame()
            
            # Yield results for this batch
            for _, row in df.iterrows():
                try:
                    recent_messages = get_recent_messages_for_chat(db_path, int(row['chat_id']), limit=5)
                    
                    result = {
                        "chat_id": int(row['chat_id']),
                        "name": row['display_name'] or row['chat_identifier'],
                        "chat_identifier": row['chat_identifier'],
                        "members": int(row['member_count']) if pd.notna(row['member_count']) else 0,
                        "total_messages": int(row['message_count']),
                        "user_messages": int(row['user_message_count']) if pd.notna(row['user_message_count']) else 0,
                        "last_message_date": row['last_message_date'],
                        "recent_messages": recent_messages
                    }
                    
                    yield result
                except Exception as e:
                    logger.error(f"Error processing chat {row.get('chat_id', 'unknown')}: {e}", exc_info=True)
                    # Continue with next chat instead of crashing
                    continue
    
    except Exception as e:
        logger.error(f"Error in advanced_chat_search_streaming: {e}", exc_info=True)
        # Re-raise to be caught by the endpoint
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing database connection: {e}")
