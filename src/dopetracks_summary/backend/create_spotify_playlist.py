import sqlite3
from dotenv import load_dotenv
import os
import spotipy as sp
import pandas as pd
import logging
import dopetracks_summary.backend.spotify_db_manager as sdm
from spotipy.oauth2 import SpotifyOAuth
import dopetracks_summary.backend.spotify_db_manager as sdm


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
        sp (spotipy.Spotify): Authenticated Spotify client instance.
        playlist_id (str): The ID of the Spotify playlist.
        track_ids (list): List of Spotify track IDs to add.
    """

    # Step 1: Get existing tracks in the playlist
    existing_tracks = []
    results = sp.playlist_items(
        playlist_id,
        fields="items.track.id,total",
        additional_types=["track"]
    )
    
    # Use a while loop to gather *all* tracks in the playlist.
    # If 'next' isn't present, break out of the loop.
    while results:
        # Safely extract 'items' (in case it's missing or None)
        items = results.get("items", [])
        existing_tracks.extend(
            item["track"]["id"] for item in items if item.get("track")
        )

        # Check for 'next' safely:
        next_url = results.get("next")
        if next_url:
            results = sp.next(results)  # Grab the next page
        else:
            break

    # Step 2: Filter out tracks already in the playlist
    unique_track_ids = [track_id for track_id in track_ids if track_id not in existing_tracks]
    if not unique_track_ids:
        logging.info("No new tracks to add; all tracks are already in the playlist.")
        return


     # Step 3: Add the unique tracks to the playlist in batches of 100
    for i in range(0, len(unique_track_ids), 100):
        batch = unique_track_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)
    logging.info(f"Added {len(unique_track_ids)} new tracks to the playlist.")

def get_all_playlist_items(sp, playlist_id: str) -> list[dict]:
    """
    Return *all* items from a given playlist, handling Spotify's pagination
    behind the scenes.
    
    Args:
        sp (spotipy.Spotify): Authenticated Spotify client instance.
        playlist_id (str): The Spotify playlist ID.

    Returns:
        A list of playlist item dictionaries (each containing 'track', etc.).
    """
    all_items = []
    limit = 100
    offset = 0

    while True:
        response = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset,
            fields="items.track.id, total, next",
            additional_types=["track"]
        )

        items = response.get("items", [])
        all_items.extend(items)

        # If we’ve reached the end or there's no 'next' in the response, break
        if not response.get("next"):
            break

        # Otherwise, increase offset to get the next page
        offset += limit

    return all_items


def get_song_ids_from_spotify_items(playlist_items: list[dict]) -> list[str]:
    """
    Extract Spotify track IDs from a list of playlist items.
    
    Args:
        playlist_items (list[dict]): List of Spotify playlist item dictionaries.

    Returns:
        A list of Spotify track IDs.
    """
    return [item["track"]["id"] for item in playlist_items if item.get("track")]


def get_song_ids_from_cached_urls(track_original_urls_list):
    """
    Retrieve Spotify track IDs from the cache based on the original URLs.
    
    Args:
        conn_cache (sqlite3.Connection): SQLite database connection.
        track_original_urls_list (list[str]): List of Spotify original URLs.

    Returns:
        A list of Spotify track IDs.
    """

    conn_cache = sqlite3.connect(sdm.initialize_cache())
    placeholders = ', '.join('?' for _ in track_original_urls_list)  # Generate placeholders
    query = f"""
    SELECT DISTINCT spotify_id
    FROM spotify_url_cache
    WHERE EXISTS (
        SELECT 1
        FROM json_each(original_url)
        WHERE value IN ({placeholders})
    )
    """
    return pd.read_sql_query(query, conn_cache, params=track_original_urls_list)['spotify_id'].tolist()


def main(PLAYLIST_NAME, TRACKS_TO_ADD):
    """
    Main entry point: create or find a playlist and add tracks to it.
    
    Args:
        PLAYLIST_NAME (str): Name of the Spotify playlist.
        tracks_list (list[str]): A list of Spotify track IDs (e.g., "spotify:track:...").
    """

    logging.info(
    '''
----------------------------------------------------------
[3] Creating Spotify playlist...
----------------------------------------------------------
    ''')
    
    # Inputted songs
    spotify_ids_to_add = get_song_ids_from_cached_urls(TRACKS_TO_ADD)

    # Existing songs in playlist
    sp = sdm.authenticate_spotify(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)
    user_id = get_user_id(sp)
    playlist = find_or_create_playlist(sp, user_id, PLAYLIST_NAME, public=True)
    existing_playlist_songs = get_all_playlist_items(sp, playlist['id'])
    existing_playlist_song_ids = get_song_ids_from_spotify_items(existing_playlist_songs)
    
    # New songs to add
    unique_ids = [tid for tid in spotify_ids_to_add if tid not in existing_playlist_song_ids]
    
    # Add songs
    add_tracks_to_playlist(sp, playlist['id'], unique_ids)

if __name__ == "__main__":
    main()
