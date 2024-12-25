import sqlite3
import pandas as pd
from typing import Optional
import dopetracks_summary.utility_functions as uf
import logging
import typedstream
import time

# Configure logging with timestamps
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'  # Optional: Customize the timestamp format
)

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


def add_reaction_type(messages):
    ''' Adds a column to the messages DataFrame with the reaction type'''
    messages['reaction_type'] = messages['associated_message_type'].apply(uf.detect_reaction)
    return messages

def get_chat_size(handles_list):
    '''
    Given the list of handles in a chat thread, returns the size of the list, i.e., the number of unique handles in the chat. 
    '''
    if handles_list is None:
        return 0
    else:
        return len(handles_list)

def merge_chat_data(messages_raw, chat_message_joins):
    """
    Adds chat IDs for each message ID.

    Args:
        messages_raw (DataFrame): Messages DataFrame.
        chat_message_joins (DataFrame): Chat-Message join DataFrame.

    Returns:
        DataFrame: Merged DataFrame with chat IDs.
    """
    return pd.merge(messages_raw, chat_message_joins, how='left', on='message_id')


def enrich_messages_with_chat_info(messages, handles, chat_handle_join):
    """
    Enriches the messages DataFrame with chat member handles and contact info.

    Args:
        messages (pd.DataFrame): The DataFrame containing message data.
        handle_contact_list_per_chat (pd.DataFrame): DataFrame with grouped contact info for chats.
        chat_handle_join (pd.DataFrame): DataFrame with chat-handle relationships

    Returns:
        pd.DataFrame: Updated messages DataFrame with chat member info and chat size.
    """
    messages = pd.merge(messages, handles[['handle_id', 'contact_info']], on='handle_id', how='left')

    chat_handle_contact_info =  pd.merge(chat_handle_join, handles[['handle_id', 'contact_info']], on='handle_id', how='left')

    handle_contact_list_per_chat = pd.DataFrame({
        'chat_members_handles': chat_handle_contact_info.groupby('chat_id')['handle_id'].unique(),
        'chat_members_contact_info': chat_handle_contact_info.groupby('chat_id')['contact_info'].unique()
    }).reset_index()

    messages = pd.merge(messages, handle_contact_list_per_chat, on='chat_id', how='left')
    messages['chat_members_handles'] = messages['chat_members_handles'].fillna('')
    messages['chat_members_contact_info'] = messages['chat_members_contact_info'].fillna('')
    messages['chat_size'] = messages['chat_members_handles'].apply(lambda x: len(x) if isinstance(x, (list, set, pd.Series)) else 0)
    return messages


def parse_AttributeBody(data):
    """
    Parse a binary attributedBody message and extract all components dynamically.

    Parameters:
        data (bytes): Serialized binary data.

    Returns:
        dict: Extracted text, metadata, and all component values.
    """
    result = {"text": None, "metadata": {}, "components": {}}

    try:
        if not data:  # Handle empty or invalid binary data
            return result

        # Parse the binary data
        ts = typedstream.unarchive_from_data(data)

        # Debug: Inspect parsed contents
        for c in ts.contents:
            if hasattr(c, 'values'):
                for v in c.values:
                    # Dynamically collect all components with archived_name and value
                    if hasattr(v, 'archived_name') and hasattr(v, 'value') and v.value is not None:
                        result["components"][v.archived_name] = v.value

        # Prioritize NSString and NSMutableString for the "text" field
        for key in (b'NSString', b'NSMutableString'):
            if key in result["components"]:
                result["text"] = result["components"][key]
                break
            
        # Additional metadata extraction (if needed)
        for content in ts.contents:
            if hasattr(content, 'value') and isinstance(content.value, dict):
                result["metadata"].update(content.value)

    except Exception as e:
        print(f"Error parsing binary message: {e}")

    return result


def finalize_text(messages):
    """
    Assignes a final text value using the extracted text from the attributedBody as
    well as the text from the text field.

    Args:
        messages (DataFrame): DataFrame containing messages data.

    Returns:
        DataFrame: Updated DataFrame with final text values.
    """
    messages['final_text'] = messages.apply(
        lambda row: row['text'] if pd.notna(row['text']) 
        else row['extracted_text'].get('text', None) if isinstance(row['extracted_text'], dict) 
        else None,
    axis=1)
    return messages


def append_links_columns(df, message_column):
    """
    Extracts Spotify links, YouTube links, shortened URLs, and other URLs from a specified column,
    categorizes them, and appends the results as new columns to the DataFrame.

    Parameters:
        df (pd.DataFrame): The input DataFrame.
        message_column (str): The column name containing message text to extract links from.

    Returns:
        pd.DataFrame: The updated DataFrame with new columns for categorized links.
    """

    # Flexible regex for links (handles http, https, and shortened URLs)
    spotify_regex = r'(https?://open\.spotify\.com/[^\s]+|open\.spotify\.com/[^\s]+|https?://spotify\.link/[^\s]+)'
    youtube_regex = r'(https?://(?:www\.)?youtube\.com/[^\s]+|https?://youtu\.be/[^\s]+|youtube\.com/[^\s]+|youtu\.be/[^\s]+)'
    general_url_regex = r'(https?://(?:bit\.ly|tinyurl\.com|t\.co|buff\.ly|short\.io|lnkd\.in)/[^\s]+|(?:bit\.ly|tinyurl\.com|t\.co|buff\.ly|short\.io|lnkd\.in)/[^\s]+|((https?|www)\://[^\s]+|[^\s]+\.[a-z]{2,}/[^\s]*))'


     # Extract links
    spotify_links = df[message_column].str.extractall(spotify_regex)[0].dropna()
    youtube_links = df[message_column].str.extractall(youtube_regex)[0].dropna()
    general_links = df[message_column].str.extractall(general_url_regex)[0].dropna()

    
    # Categorize Spotify links
    df['spotify_song_links'] = spotify_links[spotify_links.str.contains('/track/')].groupby(level=0).apply(list)
    df['spotify_album_links'] = spotify_links[spotify_links.str.contains('/album/')].groupby(level=0).apply(list)
    df['spotify_playlist_links'] = spotify_links[spotify_links.str.contains('/playlist/')].groupby(level=0).apply(list)
    df['spotify_other_links'] = spotify_links[~spotify_links.str.contains('/track/|/album/|/playlist/')].groupby(level=0).apply(list)

    # Add YouTube links
    df['youtube_links'] = youtube_links.groupby(level=0).apply(list)

    # Add general links (exclude Spotify and YouTube links to avoid duplication)
    df['general_links'] = general_links[~general_links.isin(spotify_links) & 
                                        ~general_links.isin(youtube_links)].groupby(level=0).apply(list)

    # Fill NaN values with empty lists for cleaner handling downstream
    for column in ['spotify_song_links', 'spotify_album_links', 'spotify_playlist_links', 
                   'spotify_other_links', 'youtube_links', 'general_links']:
        df[column] = df[column].apply(lambda x: x if isinstance(x, list) else [])

    return df

def pull_and_clean_messages(db_path: Optional[str] = None):
    """Main function to pull data."""
    if db_path is None:
        db_path = "/Users/nmarks/Library/Messages/chat.db"  # Default path

    logging.info(
    '''
    ----------------------------------------------------------
    [1] Pulling and cleaning iMessage data
    ----------------------------------------------------------
    ''')
    logging.info("Connecting to the database...")
    start_time = time.time()
    try:
        conn_messages = connect_to_database(db_path)
        db_connection_established = time.time()
        logging.info(f"Database connection established. Time taken: {db_connection_established - start_time:.2f}s")


        logging.info("Pulling data...")        
        messages = fetch_messages(conn_messages)
        handles = fetch_handles(conn_messages)
        chat_message_join = fetch_chat_message_join(conn_messages)
        chat_handle_join = fetch_chat_handle_join(conn_messages)
        attachments = fetch_attachments(conn_messages)
        data_pulled = time.time()
        logging.info(f"Data successfully pulled! Time taken: {data_pulled - db_connection_established:.2f}s")

        logging.info("Cleaning data...")
        messages, handles = rename_columns(messages, handles)
        messages = merge_chat_data(messages, chat_message_join)
        messages = convert_timestamps(messages)
        messages = enrich_messages_with_chat_info(messages, handles, chat_handle_join)
        messages = add_reaction_type(messages)
        data_cleaned = time.time()
        logging.info(f"Data successfully cleaned! Time taken: {data_cleaned - data_pulled:.2f}s")

        logging.info("Parsing AttributedBody...")
        messages['extracted_text'] = messages['attributedBody'].apply(parse_AttributeBody)
        messages = finalize_text(messages)
        attributed_body_parsed = time.time()
        logging.info(f"Done parsing AttributedBody! Time taken: {attributed_body_parsed - data_cleaned:.2f}s")


        logging.info("Extracting Spotify and other links...")
        messages = append_links_columns(messages, 'final_text')
        spotify_links_extracted = time.time()
        logging.info(f"Spotify and other links extracted! Time taken: {spotify_links_extracted - attributed_body_parsed:.2f}s")

        # For demonstration, return all datasets as a dictionary
        return {
            "messages": messages,
            "handles": handles,
            "chat_message_join": chat_message_join,
            "chat_handle_join": chat_handle_join,
            "attachments": attachments,
        }
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        if conn_messages:
            conn_messages.close()
            logging.info("Messages database connection (chat.db) closed.")



if __name__ == "__main__":
    data = pull_and_clean_messages()