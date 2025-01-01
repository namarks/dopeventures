from dotenv import load_dotenv
import os
import spotipy as sp
import pandas as pd
import logging
from spotipy.oauth2 import SpotifyOAuth
import dopetracks_summary.spotify_db_manager as sdm


CLIENT_ID=os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET=os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI=os.getenv('SPOTIFY_REDIRECT_URI')
SCOPE = "playlist-modify-public playlist-modify-private"


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




def main(PLAYLIST_NAME):

    logging.info(
    '''
    ----------------------------------------------------------
    [2] Creating Spotify playlist...
    ----------------------------------------------------------
    ''')
    
    sp = sdm.authenticate_spotify(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)
    user_id = get_user_id(sp)
    playlist = find_or_create_playlist(sp, user_id, PLAYLIST_NAME, public=True)

    add_tracks_to_playlist(sp, )

if __name__ == "__main__":
    main()
