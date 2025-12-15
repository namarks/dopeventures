#!/usr/bin/env python3
"""
Compare members between two chats to see who was added or removed.
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

def get_chat_members(db_path: str, chat_id: int):
    """Get all members of a chat with their message counts."""
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT DISTINCT
            handle.id as contact_info,
            handle.ROWID as handle_id,
            COUNT(DISTINCT message.ROWID) as message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        JOIN message ON chat_message_join.message_id = message.ROWID
        LEFT JOIN handle ON message.handle_id = handle.ROWID
        WHERE chat.ROWID = ?
        AND message.handle_id IS NOT NULL
        GROUP BY handle.id, handle.ROWID
        ORDER BY message_count DESC
    """
    
    members = conn.execute(query, (chat_id,)).fetchall()
    conn.close()
    
    return members

def compare_members(db_path: str, chat_id1: int, chat_id2: int):
    """Compare members between two chats."""
    # Get chat names
    conn = sqlite3.connect(db_path)
    chat1_name = conn.execute("SELECT display_name FROM chat WHERE ROWID = ?", (chat_id1,)).fetchone()[0]
    chat2_name = conn.execute("SELECT display_name FROM chat WHERE ROWID = ?", (chat_id2,)).fetchone()[0]
    conn.close()
    
    members1 = get_chat_members(db_path, chat_id1)
    members2 = get_chat_members(db_path, chat_id2)
    
    # Create sets of handle_ids for comparison
    set1 = {m[1] for m in members1}  # handle_id
    set2 = {m[1] for m in members2}  # handle_id
    
    # Find members only in chat1
    only_in_1 = [m for m in members1 if m[1] not in set2]
    
    # Find members only in chat2
    only_in_2 = [m for m in members2 if m[1] not in set1]
    
    # Find common members
    common = [m for m in members1 if m[1] in set2]
    
    print("=" * 80)
    print("MEMBER COMPARISON")
    print("=" * 80)
    print()
    print(f"Chat {chat_id1} ({chat1_name}): {len(members1)} members")
    print(f"Chat {chat_id2} ({chat2_name}): {len(members2)} members")
    print()
    
    print("=" * 80)
    print(f"MEMBERS ONLY IN CHAT {chat_id1} (DROPPED IN CHAT {chat_id2})")
    print("=" * 80)
    print()
    
    if only_in_1:
        for contact_info, handle_id, msg_count, first_date, last_date in only_in_1:
            print(f"  {contact_info or f'Handle {handle_id}'}")
            print(f"    - Messages: {msg_count:,}")
            print(f"    - First: {first_date}")
            print(f"    - Last: {last_date}")
            print()
    else:
        print("  None")
        print()
    
    print("=" * 80)
    print(f"MEMBERS ONLY IN CHAT {chat_id2} (ADDED IN CHAT {chat_id2})")
    print("=" * 80)
    print()
    
    if only_in_2:
        for contact_info, handle_id, msg_count, first_date, last_date in only_in_2:
            print(f"  {contact_info or f'Handle {handle_id}'}")
            print(f"    - Messages: {msg_count:,}")
            print(f"    - First: {first_date}")
            print(f"    - Last: {last_date}")
            print()
    else:
        print("  None")
        print()
    
    print("=" * 80)
    print(f"COMMON MEMBERS (IN BOTH CHATS)")
    print("=" * 80)
    print()
    print(f"Total: {len(common)} members")
    print()
    
    # Show common members with message counts in each chat
    for m1 in common:
        contact_info, handle_id, msg_count1, first_date1, last_date1 = m1
        # Find corresponding member in chat2
        m2 = next((m for m in members2 if m[1] == handle_id), None)
        if m2:
            msg_count2 = m2[2]
            print(f"  {contact_info or f'Handle {handle_id}'}")
            print(f"    - Chat {chat_id1}: {msg_count1:,} messages")
            print(f"    - Chat {chat_id2}: {msg_count2:,} messages")
            print()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 compare_chat_members.py <chat_id1> <chat_id2>")
        print("Example: python3 compare_chat_members.py 4198 4387")
        sys.exit(1)
    
    try:
        chat_id1 = int(sys.argv[1])
        chat_id2 = int(sys.argv[2])
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
    
    compare_members(db_path, chat_id1, chat_id2)
