#!/usr/bin/env python3
"""
Check the actual service types of messages in a chat to understand
why a chat might be classified as SMS vs iMessage.
"""
import sqlite3
import sys
import os

def find_chat_db():
    """Find the Messages database path."""
    possible_paths = [
        os.path.expanduser("~/Library/Messages/chat.db"),
        "/Users/nmarks/Library/Messages/chat.db",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def check_chat_service_details(db_path: str, chat_id: int):
    """Check service breakdown for a specific chat."""
    conn = sqlite3.connect(db_path)
    
    # Get chat info
    chat_info = conn.execute(
        "SELECT display_name, chat_identifier, service_name FROM chat WHERE ROWID = ?",
        (chat_id,)
    ).fetchone()
    
    if not chat_info:
        print(f"Chat {chat_id} not found")
        return
    
    display_name, chat_identifier, chat_service = chat_info
    print(f"Chat: {display_name} (chat_id: {chat_id})")
    print(f"Chat-level service_name: {chat_service}")
    print(f"Chat Identifier: {chat_identifier}")
    print()
    
    # Check actual message services
    query = """
        SELECT 
            message.service,
            COUNT(*) as message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_date
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        WHERE chat_message_join.chat_id = ?
        GROUP BY message.service
        ORDER BY message_count DESC
    """
    
    services = conn.execute(query, (chat_id,)).fetchall()
    
    print("=" * 80)
    print("ACTUAL MESSAGE SERVICES (from message.service field)")
    print("=" * 80)
    print()
    
    total_messages = 0
    for service, count, first_date, last_date in services:
        total_messages += count
        percentage = (count / sum(s[1] for s in services)) * 100
        print(f"Service: {service or 'NULL'}")
        print(f"  Messages: {count:,} ({percentage:.1f}%)")
        print(f"  Date Range: {first_date} to {last_date}")
        print()
    
    print(f"Total Messages: {total_messages:,}")
    print()
    
    # Check if messages have is_from_me and service breakdown
    print("=" * 80)
    print("SERVICE BREAKDOWN BY SENDER")
    print("=" * 80)
    print()
    
    sender_query = """
        SELECT 
            message.service,
            message.is_from_me,
            COUNT(*) as message_count
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        WHERE chat_message_join.chat_id = ?
        GROUP BY message.service, message.is_from_me
        ORDER BY message.service, message.is_from_me
    """
    
    sender_services = conn.execute(sender_query, (chat_id,)).fetchall()
    
    for service, is_from_me, count in sender_services:
        sender = "You" if is_from_me else "Others"
        print(f"{service or 'NULL'} - {sender}: {count:,} messages")
    
    print()
    
    # Check recent messages and their services
    print("=" * 80)
    print("RECENT MESSAGES WITH SERVICE INFO")
    print("=" * 80)
    print()
    
    recent_query = """
        SELECT 
            message.text,
            message.service,
            message.is_from_me,
            datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc
        FROM message
        JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
        WHERE chat_message_join.chat_id = ?
        AND message.text IS NOT NULL
        AND message.text != ''
        ORDER BY message.date DESC
        LIMIT 10
    """
    
    recent = conn.execute(recent_query, (chat_id,)).fetchall()
    
    for text, service, is_from_me, date in recent:
        sender = "You" if is_from_me else "Other"
        text_preview = text[:50] + "..." if len(text) > 50 else text
        print(f"[{date}] {sender} ({service or 'NULL'}): {text_preview}")
    
    print()
    
    # Explanation
    print("=" * 80)
    print("EXPLANATION")
    print("=" * 80)
    print()
    print("The 'service_name' field in the chat table is often set based on:")
    print("  - The service of the first message")
    print("  - The most common service in the chat")
    print("  - Or may not update when the chat switches services")
    print()
    print("Blue bubbles in Messages app = iMessage")
    print("Green bubbles in Messages app = SMS/MMS")
    print()
    print("If you see blue bubbles but database shows SMS:")
    print("  - The chat may have mixed services (some iMessage, some SMS)")
    print("  - The chat.service_name field may be outdated")
    print("  - Check the actual message.service field for accuracy")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 check_chat_service.py <chat_id>")
        print("Example: python3 check_chat_service.py 4387")
        sys.exit(1)
    
    try:
        chat_id = int(sys.argv[1])
    except ValueError:
        print("Error: chat_id must be an integer")
        sys.exit(1)
    
    db_path = find_chat_db()
    if not db_path:
        print("Error: Could not find chat.db")
        sys.exit(1)
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    print(f"Using database: {db_path}")
    print()
    
    check_chat_service_details(db_path, chat_id)
