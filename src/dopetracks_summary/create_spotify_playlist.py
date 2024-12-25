from dotenv import load_dotenv
import os
import spotipy
import pandas as pd
import logging
from spotipy.oauth2 import SpotifyOAuth
from dopetracks_summary.cache_manager import load_from_cache, save_to_cache



def authenticate_spotify(client_id, client_secret, redirect_uri, scope):
    """
    Authenticate with Spotify and return a Spotipy client instance.

    Args:
        client_id (str): Spotify Client ID.
        client_secret (str): Spotify Client Secret.
        redirect_uri (str): Redirect URI for OAuth.
        scope (str): Scopes required for Spotify API access.

    Returns:
        spotipy.Spotify: Authenticated Spotipy client instance.
    """
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope
    ))


def get_user_id(sp):
    """
    Retrieve the current user's Spotify user ID.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.

    Returns:
        str: Spotify user ID.
    """
    user = sp.current_user()
    return user['id']


def find_playlist(sp, user_id, playlist_name):
    """
    Check if a playlist with the specified name already exists.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.
        user_id (str): Spotify user ID.
        playlist_name (str): Name of the playlist to search for.

    Returns:
        dict or None: Playlist details if found, otherwise None.
    """
    playlists = sp.user_playlists(user=user_id)
    while playlists:
        for playlist in playlists['items']:
            if playlist['name'] == playlist_name:
                return playlist
        # Handle pagination
        playlists = sp.next(playlists) if playlists['next'] else None
    return None


def create_playlist(sp, user_id, playlist_name, public=True):
    """
    Create a new playlist.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.
        user_id (str): Spotify user ID.
        playlist_name (str): Name of the playlist to create.
        public (bool): Whether the playlist should be public.

    Returns:
        dict: Details of the created playlist.
    """
    return sp.user_playlist_create(user=user_id, name=playlist_name, public=public)


def find_or_create_playlist(sp, user_id, playlist_name, public=True):
    """
    Find an existing playlist or create a new one.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.
        user_id (str): Spotify user ID.
        playlist_name (str): Name of the playlist to find or create.
        public (bool): Whether the playlist should be public.

    Returns:
        dict: Playlist details.
    """
    playlist = find_playlist(sp, user_id, playlist_name)
    if playlist:
        print(f"Playlist '{playlist_name}' already exists with ID: {playlist['id']}")
        return playlist
    print(f"Creating new playlist: '{playlist_name}'")
    return create_playlist(sp, user_id, playlist_name, public)

# Function to resolve shortened Spotify URLs
def resolve_shortened_url(url):
    try:
        response = requests.head(url, allow_redirects=True)
        if response.status_code == 200:
            return response.url
        else:
            return url
    except requests.RequestException:
        return url



def get_track_ids(df: pd.DataFrame, column_name):
    """
    Extract track IDs from Spotify links in the dataset.

    Args:
        df (pd.DataFrame): Dataset containing Spotify links.
        column_name (str): The column containing Spotify track links.

    Returns:
        list: List of track IDs.
    """
    track_ids = df[column_name].str.extract(r'/track/([a-zA-Z0-9]+)')[0].dropna().tolist()
    return track_ids

def get_playlist_id_by_name(sp, user_id, playlist_name):
    """
    Get the playlist ID for a given playlist name and user ID.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.
        user_id (str): Spotify user ID of the playlist creator.
        playlist_name (str): Name of the playlist to search for.

    Returns:
        str or None: The playlist ID if found, otherwise None.
    """
    # Get all playlists for the user
    playlists = sp.user_playlists(user=user_id)
    while playlists:
        for playlist in playlists['items']:
            if playlist['name'].lower() == playlist_name.lower():  # Case-insensitive match
                return playlist['id']
        # Handle pagination
        playlists = sp.next(playlists) if playlists['next'] else None
    return None  # Playlist not found


def add_tracks_to_playlist(sp, playlist_id, track_ids):
    """
    Add tracks to a Spotify playlist.

    Args:
        sp (spotipy.Spotify): Authenticated Spotipy client instance.
        playlist_id (str): The ID of the Spotify playlist.
        track_ids (list): List of Spotify track IDs to add.
    """
    for i in range(0, len(track_ids), 100):  # Spotify API supports adding 100 tracks at a time
        sp.playlist_add_items(playlist_id, track_ids[i:i+100])
    print(f"Added {len(track_ids)} tracks to the playlist.")

def fetch_spotify_metadata_with_cache(spotify_client, url, cursor):
    """
    Fetch metadata for a Spotify URL using the Spotify API, with SQLite cache.

    Args:
        spotify_client (spotipy.Spotify): Authenticated Spotify client.
        url (str): Spotify URL.
        cursor (sqlite3.Cursor): SQLite cursor for cache.

    Returns:
        dict: Metadata for the Spotify entity.
    """
    cached_metadata = load_from_cache(cursor, url)
    if cached_metadata:
        logging.info(f"Using cached metadata for: {url}")
        return cached_metadata

    try:
        path_parts = re.search(r'open\\.spotify\\.com/(track|album|playlist|artist|show|episode)/([\\w\\d]+)', url)
        if not path_parts:
            return None
        entity_type, entity_id = path_parts.groups()

        if entity_type == "track":
            metadata = spotify_client.track(entity_id)
        elif entity_type == "album":
            metadata = spotify_client.album(entity_id)
        elif entity_type == "playlist":
            metadata = spotify_client.playlist(entity_id)
        elif entity_type == "artist":
            metadata = spotify_client.artist(entity_id)
        elif entity_type == "show":
            metadata = spotify_client.show(entity_id)
        elif entity_type == "episode":
            metadata = spotify_client.episode(entity_id)
        else:
            return None

        save_to_cache(cursor, url, metadata)
        logging.info(f"Fetched and cached metadata for: {url}")
        return metadata
    except Exception as e:
        logging.error(f"Error fetching metadata for {url}: {e}")
        return None

def create_spotify_playlist(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE, PLAYLIST_NAME):
    # Authenticate with Spotify
    sp = authenticate_spotify(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)

    # Get Spotify user ID
    user_id = get_user_id(sp)

    # Find or create playlist
    playlist = find_or_create_playlist(sp, user_id, PLAYLIST_NAME, public=True)

    # # Extract track IDs from a specific column in the dataset
    # track_ids = get_track_ids(messages, column_name='spotify_links')  # Replace 'spotify_links' with your column name

    # # Add tracks to the playlist
    # add_tracks_to_playlist(sp, playlist_id, track_ids)


if __name__ == "__main__":
    # data = pull_data.pull_and_clean_messages()

    logging.info(
    '''
    ----------------------------------------------------------
    [2] Creating Spotify playlist...
    ----------------------------------------------------------
    ''')
    # Input spotify API credentials + playlist name
    CLIENT_ID=os.getenv('SPOTIFY_CLIENT_ID')
    CLIENT_SECRET=os.getenv('SPOTIFY_CLIENT_SECRET')
    REDIRECT_URI=os.getenv('SPOTIFY_REDIRECT_URI')
    SCOPE = "playlist-modify-public playlist-modify-private"
    PLAYLIST_NAME = 'Dopetracks Generated Playlist'


    # Authenticate with Spotify
    sp = authenticate_spotify(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)

    # Get Spotify user ID
    user_id = get_user_id(sp)

    # Find or create playlist
    playlist = find_or_create_playlist(sp, user_id, PLAYLIST_NAME, public=True)

