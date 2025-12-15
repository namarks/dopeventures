#!/usr/bin/env python3
"""
Compare two chat entries by chat_id to understand their differences.
Helps identify which chat entry to use when there are duplicates.
"""
import sqlite3
import sys
import os
from pathlib import Path

def find_chat_db():
    """Find the Messages database path."""
    # Common locations
    possible_paths = [
        os.path.expanduser("~/Library/Messages/chat.db"),
        "/Users/nmarks/Library/Messages/chat.db",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try to get from environment or ask user
    db_path = os.environ.get("MESSAGES_DB_PATH")
    if db_path and os.path.exists(db_path):
        return db_path
    
    print("Could not find chat.db automatically.")
    print("Please provide the path to ~/Library/Messages/chat.db")
    return None

def compare_chats(db_path: str, chat_id1: int, chat_id2: int):
    """Compare two chat entries in detail."""
    conn = sqlite3.connect(db_path)
    
    # Get basic chat info
    query = """
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            chat.GUID,
            chat.service_name,
            COUNT(DISTINCT message.ROWID) as message_count,
            COUNT(DISTINCT message.handle_id) as member_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date,
            COUNT(DISTINCT CASE WHEN message.is_from_me = 1 THEN message.ROWID END) as user_message_count
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.ROWID IN (?, ?)
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier, chat.GUID, chat.service_name
        ORDER BY chat.ROWID
    """
    
    df = conn.execute(query, (chat_id1, chat_id2)).fetchall()
    
    if len(df) != 2:
        print(f"Error: Could not find both chats. Found {len(df)} matches.")
        conn.close()
        return
    
    print("=" * 80)
    print("CHAT COMPARISON")
    print("=" * 80)
    print()
    
    # Display info for each chat
    for i, row in enumerate(df, 1):
        chat_id, display_name, chat_identifier, guid, service_name, message_count, member_count, first_date, last_date, user_msg_count = row
        
        print(f"CHAT {i} (chat_id: {chat_id})")
        print("-" * 80)
        print(f"  Display Name:      {display_name}")
        print(f"  Chat Identifier:   {chat_identifier}")
        print(f"  GUID:              {guid}")
        print(f"  Service:           {service_name}")
        print(f"  Total Messages:    {message_count:,}")
        print(f"  Your Messages:     {user_msg_count:,}")
        print(f"  Member Count:      {member_count}")
        print(f"  First Message:     {first_date}")
        print(f"  Last Message:      {last_date}")
        print()
    
    # Get member details for each chat
    print("=" * 80)
    print("MEMBERS COMPARISON")
    print("=" * 80)
    print()
    
    for chat_id in [chat_id1, chat_id2]:
        member_query = """
            SELECT DISTINCT
                handle.id as contact_info,
                handle.ROWID as handle_id,
                COUNT(DISTINCT message.ROWID) as message_count
            FROM chat
            JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
            JOIN message ON chat_message_join.message_id = message.ROWID
            LEFT JOIN handle ON message.handle_id = handle.ROWID
            WHERE chat.ROWID = ?
            AND message.handle_id IS NOT NULL
            GROUP BY handle.id, handle.ROWID
            ORDER BY message_count DESC
        """
        
        members = conn.execute(member_query, (chat_id,)).fetchall()
        
        print(f"Chat {chat_id} Members ({len(members)} unique):")
        for contact_info, handle_id, msg_count in members[:10]:  # Show top 10
            print(f"  - {contact_info or f'Handle {handle_id}'} ({msg_count:,} messages)")
        if len(members) > 10:
            print(f"  ... and {len(members) - 10} more")
        print()
    
    # Get recent messages from each chat
    print("=" * 80)
    print("RECENT MESSAGES COMPARISON")
    print("=" * 80)
    print()
    
    for chat_id in [chat_id1, chat_id2]:
        recent_query = """
            SELECT 
                message.text,
                message.is_from_me,
                datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
            FROM message
            JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
            WHERE chat_message_join.chat_id = ?
            AND message.text IS NOT NULL
            AND message.text != ''
            ORDER BY message.date DESC
            LIMIT 5
        """
        
        recent = conn.execute(recent_query, (chat_id,)).fetchall()
        
        print(f"Chat {chat_id} - 5 Most Recent Messages:")
        for text, is_from_me, date in recent:
            sender = "You" if is_from_me else "Other"
            text_preview = text[:60] + "..." if len(text) > 60 else text
            print(f"  [{date}] {sender}: {text_preview}")
        print()
    
    # Check if they share any messages (might be split/merged chats)
    overlap_query = """
        SELECT COUNT(DISTINCT message.ROWID) as shared_messages
        FROM message
        JOIN chat_message_join cmj1 ON message.ROWID = cmj1.message_id AND cmj1.chat_id = ?
        JOIN chat_message_join cmj2 ON message.ROWID = cmj2.message_id AND cmj2.chat_id = ?
    """
    
    overlap = conn.execute(overlap_query, (chat_id1, chat_id2)).fetchone()[0]
    
    print("=" * 80)
    print("RELATIONSHIP ANALYSIS")
    print("=" * 80)
    print(f"Shared Messages: {overlap:,}")
    
    if overlap > 0:
        print("⚠️  These chats share messages - they may be related (split/merged chat)")
    else:
        print("✓ These chats have no shared messages - they are separate conversations")
    
    print()
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 compare_chats.py <chat_id1> <chat_id2>")
        print("Example: python3 compare_chats.py 4198 4387")
        sys.exit(1)
    
    try:
        chat_id1 = int(sys.argv[1])
        chat_id2 = int(sys.argv[2])
    except ValueError:
        print("Error: chat_id must be an integer")
        sys.exit(1)
    
    db_path = find_chat_db()
    if not db_path:
        sys.exit(1)
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    print(f"Using database: {db_path}")
    print()
    
    compare_chats(db_path, chat_id1, chat_id2)
