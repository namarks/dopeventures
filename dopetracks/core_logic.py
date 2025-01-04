import logging
from typing import Optional
import pandas as pd
from dopetracks import prepare_data_main
from dopetracks import spotify_db_manager as sdm
from dopetracks import utility_functions as uf
from dopetracks import create_spotify_playlist as csp
from dopetracks import generate_summary_stats as gss

def processs_user_inputs(start_date = '2025-01-01', 
                         end_date = '2025-01-05', 
                         playlist_name = 'tester playlist', 
                         filepath=None, 
                         chat_name_text: Optional[str] = None):
    
    '''
    --------------------------------------------------------------------------------------------------------------------
    Initializing Run of Dopetracks Summary package
    --------------------------------------------------------------------------------------------------------------------
    '''
    # Generalized messages_db_path
    if filepath:
        messages_db_path = filepath
        logging.info(f"Using inputed filepath: {messages_db_path}")

    else: 
        messages_db_path = uf.get_messages_db_path()
        logging.info(f"Using default messages_db_path: {messages_db_path}")
    
    # Step 1: Pull and clean data
    data = prepare_data_main.pull_and_clean_messages(messages_db_path)


    # Step 2: Get Spotify URL metadata and cache URls
    sdm.main(data['messages'], 'all_spotify_links')
    

    # Step 3: Create Spotify playlist and add tracks
    # Name of playlist to generate
    PLAYLIST_NAME = playlist_name

    # Tracks to include in playlist
    filtered_messages = data['messages'][
        (data['messages']['date'] >= start_date) &
        (data['messages']['date'] <= end_date) &
        (data['messages']['spotify_song_links'].apply(len) > 0)
    ]

    # Apply chat name filter only if `chat_name_text` is provided
    if chat_name_text:
        filtered_messages = filtered_messages[
            filtered_messages['chat_name']
            .apply(lambda x: isinstance(x, str) and f"{chat_name_text}".lower() in x.lower())
        ]

    # Extract unique Spotify song links
    track_original_urls_list = (
        filtered_messages
        .explode('spotify_song_links')['spotify_song_links']
        .unique()
        .tolist()
    )
    
    csp.main(PLAYLIST_NAME, track_original_urls_list)
    

    # Setp 4: Generate summary statistics
    # summary = gss.main(data)  
if __name__ == '__main__':
    processs_user_inputs()