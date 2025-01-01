import os
import logging
from dopetracks_summary.data_prep import prepare_data_main
from dopetracks_summary.data_prep import spotify_db_manager as sdm
from dopetracks_summary import utility_functions as uf
import dopetracks_summary.data_prep.spotify_db_manager as sdm

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

    print(data['messages'].head())

    # Step 2: Get Spotify URL metadata and cache URls
    sdm.main(data['messages'], 'all_spotify_links')

    # Step 3: Create Spotify playlist and add tracks

    # Name of playlist to generate
    PLAYLIST_NAME = 'Dopetracks Generated Playlist'

    
    '''
    TODO: update to accept multiple playlist names as input, each with their own lookup definition. 
        i created this package to create a playlist with all songs sent in my friends music
        group chat (Dopetracks) in 2024, but it'd be nice to also generate playlists for any chat or custom
        filter of message. for example i could create a playlist of songs sent to me in _any_ iMessage chat
    '''

if __name__ == "__main__":
    main()
