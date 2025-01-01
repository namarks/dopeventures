import pandas as pd
import typedstream
import dopetracks_summary.dictionaries as dictionaries

def detect_reaction(associated_message_type):
    ''' Detect and translate whether the iMessage was a reaction'''
    if associated_message_type in dictionaries.reaction_dict.keys():
        return dictionaries.reaction_dict[associated_message_type]
    else:
        return 'no-reaction'
    

def add_reaction_type(messages):
    ''' Adds a column to the messages DataFrame with the reaction type'''
    messages['reaction_type'] = messages['associated_message_type'].apply(detect_reaction)
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
    # messages = pd.merge(messages, handles[['handle_id', 'contact_info']], on='handle_id', how='left')

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
    spotify_regex = r'((https?://open\.spotify\S+|https?://spotify.link\S+))'
    youtube_regex = r'(https?://(?:www\.)?youtube\.com/[^\s]+|https?://youtu\.be/[^\s]+|youtube\.com/[^\s]+|youtu\.be/[^\s]+)'
    general_url_regex = r'(https?://(?:bit\.ly|tinyurl\.com|t\.co|buff\.ly|short\.io|lnkd\.in)/[^\s]+|(?:bit\.ly|tinyurl\.com|t\.co|buff\.ly|short\.io|lnkd\.in)/[^\s]+|((https?|www)\://[^\s]+|[^\s]+\.[a-z]{2,}/[^\s]*))'


     # Extract links
    spotify_links = df[df['reaction_type'] == 'no-reaction'][message_column].str.extractall(spotify_regex)[0].dropna()
    youtube_links = df[df['reaction_type'] == 'no-reaction'][message_column].str.extractall(youtube_regex)[0].dropna()
    general_links = df[df['reaction_type'] == 'no-reaction'][message_column].str.extractall(general_url_regex)[0].dropna()

    
    # Categorize Spotify links
    df['all_spotify_links'] = spotify_links.groupby(level=0).apply(list)
    df['spotify_song_links'] = spotify_links[spotify_links.str.contains('/track/')].groupby(level=0).apply(list)
    df['spotify_album_links'] = spotify_links[spotify_links.str.contains('/album/')].groupby(level=0).apply(list)
    df['spotify_playlist_links'] = spotify_links[spotify_links.str.contains('/playlist/')].groupby(level=0).apply(list)
    df['spotify_artist_links'] = spotify_links[spotify_links.str.contains('/artist/')].groupby(level=0).apply(list)
    df['spotify_episode_links'] = spotify_links[spotify_links.str.contains('/episode/')].groupby(level=0).apply(list)
    df['spotify_shows_links'] = spotify_links[spotify_links.str.contains('/show/')].groupby(level=0).apply(list)
    
    
    df['spotify_other_links'] = spotify_links[~spotify_links.str.contains('/track/|/album/|/playlist/|/artist/|/episode/|/show/')].groupby(level=0).apply(list)

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