#!/usr/bin/env python3
"""
Debug script to investigate duplicate chat names in Messages database.
"""
import sqlite3
import sys
from pathlib import Path

def find_chat_duplicates(db_path: str, chat_name: str):
    """Find all entries for a specific chat name."""
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            chat.ROWID as chat_id,
            chat.display_name,
            chat.chat_identifier,
            chat.guid,
            COUNT(DISTINCT message.ROWID) as message_count,
            MIN(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as first_message_date,
            MAX(datetime(message.date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime")) as last_message_date
        FROM chat
        LEFT JOIN chat_message_join ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN message ON chat_message_join.message_id = message.ROWID
        WHERE chat.display_name LIKE ?
        GROUP BY chat.ROWID, chat.display_name, chat.chat_identifier, chat.guid
        ORDER BY message_count DESC
    """
    
    results = conn.execute(query, (f'%{chat_name}%',)).fetchall()
    conn.close()
    
    print(f"\n🔍 Found {len(results)} entries for chat name containing '{chat_name}':\n")
    
    for i, row in enumerate(results, 1):
        chat_id, display_name, chat_identifier, guid, msg_count, first_date, last_date = row
        print(f"Entry {i}:")
        print(f"  Chat ID: {chat_id}")
        print(f"  Display Name: {display_name}")
        print(f"  Chat Identifier: {chat_identifier}")
        print(f"  GUID: {guid}")
        print(f"  Message Count: {msg_count}")
        print(f"  First Message: {first_date}")
        print(f"  Last Message: {last_date}")
        print()
    
    # Check if they're actually different chats or duplicates
    if len(results) > 1:
        print("📊 Analysis:")
        print(f"  - Same display_name: {len(set(r[1] for r in results)) == 1}")
        print(f"  - Same chat_identifier: {len(set(r[2] for r in results if r[2])) == 1}")
        print(f"  - Same GUID: {len(set(r[3] for r in results if r[3])) == 1}")
        print(f"  - Different chat_ids: {len(set(r[0] for r in results))}")
        
        # Check message overlap
        print("\n  Message overlap check:")
        conn = sqlite3.connect(db_path)
        for i, row in enumerate(results, 1):
            chat_id = row[0]
            msg_ids = conn.execute(
                "SELECT DISTINCT message_id FROM chat_message_join WHERE chat_id = ?",
                (chat_id,)
            ).fetchall()
            print(f"    Chat {chat_id}: {len(msg_ids)} unique messages")
        conn.close()

def list_all_chats_with_name(db_path: str):
    """List all chats and show potential duplicates."""
    conn = sqlite3.connect(db_path)
    
    query = """
        SELECT 
            chat.display_name,
            COUNT(DISTINCT chat.ROWID) as chat_count,
            GROUP_CONCAT(DISTINCT chat.ROWID) as chat_ids
        FROM chat
        WHERE chat.display_name IS NOT NULL
        GROUP BY chat.display_name
        HAVING chat_count > 1
        ORDER BY chat_count DESC
        LIMIT 20
    """
    
    results = conn.execute(query).fetchall()
    conn.close()
    
    if results:
        print(f"\n⚠️  Found {len(results)} chat names with multiple entries:\n")
        for display_name, count, chat_ids in results:
            print(f"  '{display_name}': {count} entries (chat_ids: {chat_ids})")
    else:
        print("\n✅ No duplicate chat names found")

if __name__ == "__main__":
    # Try to find the database
    import os
    
    # Check common paths
    possible_paths = [
        os.path.expanduser("~/Library/Messages/chat.db"),
        f"/Users/{os.getenv('USER')}/Library/Messages/chat.db",
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ Could not find Messages database")
        print("Please provide the path as an argument:")
        print("  python3 debug_chat_duplicates.py /path/to/chat.db")
        sys.exit(1)
    
    print(f"📁 Using database: {db_path}\n")
    
    # List all duplicates
    list_all_chats_with_name(db_path)
    
    # Check specific chat if provided
    if len(sys.argv) > 1:
        chat_name = sys.argv[1]
        find_chat_duplicates(db_path, chat_name)
    else:
        print("\n💡 To check a specific chat, run:")
        print("  python3 debug_chat_duplicates.py 'dopetracks2025finalfinalFINAL.pdf'")
