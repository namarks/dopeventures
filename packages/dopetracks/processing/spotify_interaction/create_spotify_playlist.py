import sqlite3
from dotenv import load_dotenv
import os
import spotipy as sp
import pandas as pd
import logging
from typing import List, Dict
from . import spotify_db_manager as sdm
from spotipy.oauth2 import SpotifyOAuth


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

    logging.warning(f"track_ids to add (count={len(track_ids)}): {track_ids}")
    
    # Step 1: Get all existing tracks in the playlist (not just first 100)
    all_items = get_all_playlist_items(sp, playlist_id)
    existing_tracks = [item["track"]["id"] for item in all_items if item.get("track")]
    logging.warning(f"existing_tracks in playlist (count={len(existing_tracks)}): {existing_tracks}")

    # Step 2: Filter out tracks already in the playlist
    unique_track_ids = [track_id for track_id in track_ids if track_id not in existing_tracks]
    logging.warning(f"unique_track_ids to add (count={len(unique_track_ids)}): {unique_track_ids}")

    if not unique_track_ids:
        logging.info("No new tracks to add; all tracks are already in the playlist.")
        return 0  # Return 0 if nothing added

     # Step 3: Add the unique tracks to the playlist in batches of 100
    for i in range(0, len(unique_track_ids), 100):
        batch = unique_track_ids[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)
    logging.info(f"Added {len(unique_track_ids)} new tracks to the playlist.")
    return len(unique_track_ids)  # Return the count of new tracks added

def get_all_playlist_items(sp, playlist_id: str) -> List[Dict]:
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

        # If we've reached the end or there's no 'next' in the response, break
        if not response.get("next"):
            break

        # Otherwise, increase offset to get the next page
        offset += limit

    return all_items


def get_song_ids_from_spotify_items(playlist_items: List[Dict]) -> List[str]:
    """
    Extract Spotify track IDs from a list of playlist items.
    
    Args:
        playlist_items (list[dict]): List of Spotify playlist item dictionaries.

    Returns:
        A list of Spotify track IDs.
    """
    return [item["track"]["id"] for item in playlist_items if item.get("track")]


def get_song_ids_from_cached_urls(normalized_urls_list):
    """
    Retrieve Spotify track IDs from the cache based on normalized URLs.
    Args:
        normalized_urls_list (list[str]): List of normalized Spotify track URLs (no query params).
    Returns:
        A list of Spotify track IDs.
    """
    conn_cache = sqlite3.connect(sdm.initialize_cache())
    logging.info(f"Cache connected. Input normalized URLs count: {len(normalized_urls_list)}")
    
    if not normalized_urls_list:
        logging.warning("No URLs provided to get_song_ids_from_cached_urls")
        conn_cache.close()
        return []
    
    # Check what's actually in the cache
    cursor = conn_cache.cursor()
    cursor.execute("SELECT COUNT(*) FROM spotify_url_cache WHERE entity_type = 'track'")
    track_count = cursor.fetchone()[0]
    logging.info(f"Cache contains {track_count} track entries")
    
    # Check a sample of URLs in cache to see format
    cursor.execute("SELECT normalized_url, spotify_id FROM spotify_url_cache WHERE entity_type = 'track' LIMIT 3")
    samples = cursor.fetchall()
    logging.info(f"Sample cached normalized URLs: {samples}")
    
    placeholders = ', '.join('?' for _ in normalized_urls_list)  # Generate placeholders
    query = f"""
    SELECT DISTINCT spotify_id
    FROM spotify_url_cache
    WHERE normalized_url IN ({placeholders})
    AND entity_type = 'track'
    """
    
    logging.info(f"Executing query with {len(normalized_urls_list)} parameters (normalized URLs)")
    result_df = pd.read_sql_query(query, conn_cache, params=normalized_urls_list)
    logging.info(f"Query returned {len(result_df)} rows")
    
    conn_cache.close()
    return result_df['spotify_id'].tolist()


def main(PLAYLIST_NAME, TRACKS_TO_ADD):
    """
    Main entry point: create or find a playlist and add tracks to it.
    
    Args:
        PLAYLIST_NAME (str): Name of the Spotify playlist.
        tracks_list (List[str]): A list of Spotify track IDs (e.g., "spotify:track:...").
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
    added_count = add_tracks_to_playlist(sp, playlist['id'], unique_ids)
    if added_count > 0:
        print(f"Added {added_count} new tracks to the playlist.")
    else:
        print("No new tracks were added to the playlist.")

if __name__ == "__main__":
    main()
