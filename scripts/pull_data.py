import sqlite3
import pandas as pd
from typing import Optional


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


def fetch_chat_message_joins(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch message-to-chat mappings."""
    return pd.read_sql_query("SELECT * FROM chat_message_join", conn)


def fetch_chat_handle_joins(conn: sqlite3.Connection) -> pd.DataFrame:
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


def main(db_path: Optional[str] = None):
    """Main function to pull data."""
    if db_path is None:
        db_path = "/Users/nmarks/Library/Messages/chat.db"  # Default path

    try:
        conn = connect_to_database(db_path)
        print("Pulling data...")

        messages = fetch_messages(conn)
        handles = fetch_handles(conn)
        chat_message_joins = fetch_chat_message_joins(conn)
        chat_handle_joins = fetch_chat_handle_joins(conn)
        attachments = fetch_attachments(conn)

        print("Data successfully pulled!")
        # For demonstration, return all datasets as a dictionary
        return {
            "messages": messages,
            "handles": handles,
            "chat_message_joins": chat_message_joins,
            "chat_handle_joins": chat_handle_joins,
            "attachments": attachments,
        }

    finally:
        conn.close()
        print("Database connection closed.")


if __name__ == "__main__":
    data = main()
