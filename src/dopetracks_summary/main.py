
import os
from dopetracks_summary import prepare_data
from dopetracks_summary import cache_manager, create_spotify_playlist
from dopetracks_summary import utility_functions as uf

# Provide inputs for Spotify authentication and playlist creation
CLIENT_ID=os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET=os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI=os.getenv('SPOTIFY_REDIRECT_URI')
SCOPE = "playlist-modify-public playlist-modify-private"
PLAYLIST_NAME = 'Dopetracks Generated Playlist'


# Generalized messages_db_path
messages_db_path = messages_db_path = uf.get_messages_db_path()

def main():
    # Step 1: Pull and clean data
    data = prepare_data.pull_and_clean_messages(messages_db_path)
    dopetracks_data = data['messages'][(data['messages']['chat_name'] == 'Dope tracks (🔥🎧)')]

    # Step 2: Initialize SQLite cache
    conn_cachce, cursor = cache_manager.initialize_cache()

    # Step 3: Create Spotify playlist and add tracks
    create_spotify_playlist.create_spotify_playlist(
        CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE, PLAYLIST_NAME, dopetracks_data, cursor
        )
    # Close SQLite connection
    conn_cachce.close()

if __name__ == "__main__":
    main()
