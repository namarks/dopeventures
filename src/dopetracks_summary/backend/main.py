import datetime
import os
import logging
import sqlite3
import pandas as pd
from dopetracks_summary.backend import prepare_data_main
from dopetracks_summary.backend import spotify_db_manager as sdm
from dopetracks_summary import utility_functions as uf
from dopetracks_summary.backend import create_spotify_playlist as csp
from dopetracks_summary.backend import generate_summary_stats as gss

def main():

    logging.info(
'''
--------------------------------------------------------------------------------------------------------------------
Initializing Run of Dopetracks Summary package
--------------------------------------------------------------------------------------------------------------------
'''
    )

    # Generalized messages_db_path
    messages_db_path = uf.get_messages_db_path()
    
    # Step 1: Pull and clean data
    data = prepare_data_main.pull_and_clean_messages(messages_db_path)

    logging.info(data['messages'].head())

    # Step 2: Get Spotify URL metadata and cache URls
    sdm.main(data['messages'], 'all_spotify_links')
    

    # Step 3: Create Spotify playlist and add tracks
    # Name of playlist to generate
    
    PLAYLIST_NAME = 'Dope Tracks (🔥🎧) songs of 2025'
    # PLAYLIST_NAME = 'Dope Tracks (🔥🎧) songs of 2024'
    # PLAYLIST_NAME = 'Dope Tracks (🔥🎧) song, all-time'
    
    # Tracks to inclue in playlist
    track_original_urls_list = data['messages'][
        (data['messages']['chat_id'].isin([16, 286])) &
        # (data['messages']['date'] >= datetime.datetime(2024, 1, 1)) & 
        (data['messages']['date'] >= datetime.datetime(2025, 1, 1)) & 
        (data['messages']['spotify_song_links'].apply(len) > 0) & 
        (data['messages']['chat_name'].apply(lambda x: isinstance(x, str) and "dope tracks" in x.lower()))
    ].explode('spotify_song_links')['spotify_song_links'].unique().tolist()
    
    csp.main(PLAYLIST_NAME, track_original_urls_list)

    # Setp 4: Generate summary statistics
    gss.main(data)
  

if __name__ == "__main__":
    main()
