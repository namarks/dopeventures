from dotenv import load_dotenv
import os
import spotipy
import pandas as pd
import logging
from spotipy.oauth2 import SpotifyOAuth



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

def parse_spotify_url(url):
    pattern = r"open\.spotify\.com/(track|album|playlist|artist)/([\w\d]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1), match.group(2)
    return None, None

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

