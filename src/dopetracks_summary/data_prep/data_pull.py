"""
data_pull.py

This module handles the extraction of raw data from the iMessage SQLite database.

Key Functions:
- connect_to_database: Establishes a connection to the SQLite database.
- fetch_messages: Retrieves all messages from the database.
- fetch_handles: Retrieves handles (contacts) from the database.
- fetch_chat_message_join: Retrieves chat-message join table.
- fetch_chat_handle_join: Retrieves chat-handle join table.
- fetch_attachments: Retrieves attachments associated with messages.

Dependencies:
- sqlite3: For database connection and queries.
- pandas: For reading SQL query results into DataFrames.

Usage:
This module is used by pull_data.py to extract raw data. It can also be used independently 
for debugging or data inspection.

"""

import sqlite3
import pandas as pd

def connect_to_database(db_path: str) -> sqlite3.Connection:
    """Establish a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(db_path)
        print("Database connection established.")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        raise


def fetch_messages(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch all messages from the database."""
    query = '''
        SELECT *, 
            datetime(date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as date_utc 
        FROM message 
        ORDER BY date DESC
    '''
    return pd.read_sql_query(query, conn)


def fetch_handles(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch contact info (handles) from the database."""
    return pd.read_sql_query("SELECT * FROM handle", conn)


def fetch_chat_message_join(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch message-to-chat mappings."""
    return pd.read_sql_query("""
                             SELECT chat_message_join.*,
                                    chat.display_name as chat_name,
                                    chat.chat_identifier as chat_identifier
                             FROM chat_message_join
                             JOIN chat on chat_message_join.chat_id = chat.ROWID
                             """, conn)


def fetch_chat_handle_join(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch chat-to-handle mappings."""
    return pd.read_sql_query("SELECT * FROM chat_handle_join", conn)


def fetch_attachments(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch attachment information."""
    query = '''
        SELECT mime_type, filename, 
            datetime(created_date/1000000000 + strftime("%s", "2001-01-01"), "unixepoch", "localtime") as created_date, 
            message_id
        FROM attachment
        INNER JOIN message_attachment_join
        ON attachment.ROWID = attachment_id
    '''
    return pd.read_sql_query(query, conn)