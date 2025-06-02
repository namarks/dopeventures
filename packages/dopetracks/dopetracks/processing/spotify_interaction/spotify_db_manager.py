import os
import json
import logging
import time
import re
import sqlite3
import traceback
from urllib.parse import urlparse, urlunparse

import requests
import pandas as pd
import tqdm
import spotipy
from spotipy.oauth2 import SpotifyOAuth

import dopetracks.utils.utility_functions as uf

from dotenv import load_dotenv
load_dotenv()

# Load environment variables for Spotify
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPE = "playlist-modify-public playlist-modify-private"


def get_spotify_credentials() -> tuple[str, str, str]:
    """
    Fetch Spotify credentials from environment variables 
    or raise an error if not found.

    Returns:
        tuple[str, str, str]: (client_id, client_secret, redirect_uri)
    """
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise EnvironmentError("Spotify environment variables not set properly.")
    return CLIENT_ID, CLIENT_SECRET, REDIRECT_URI


def authenticate_spotify(client_id: str, client_secret: str, redirect_uri: str, scope: str) -> spotipy.Spotify:
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


def initialize_cache(db_path: str | None = None) -> str:
    """
    Initialize the Spotify cache by ensuring the directory,
    creating the database file if needed, and ensuring the
    'spotify_url_cache' table exists.
    """
    if db_path is None:
        cache_dir = os.path.expanduser("~/.spotify_cache")
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, "spotify_cache.db")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode
        cursor = conn.cursor()

        # Create a new table with the entity_type column
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS spotify_url_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT,
                normalized_url TEXT UNIQUE,
                spotify_id TEXT,
                entity_type TEXT,     
                metadata TEXT
            )
            """
        )
        conn.commit()

    return db_path



def drop_spotify_url_cache_table(db_path: str) -> None:
    """
    Drop the 'spotify_url_cache' table if it exists.

    Args:
        db_path (str): The path to the SQLite database.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS spotify_url_cache")
            logging.info("spotify_url_cache table dropped successfully.")
    except Exception as e:
        logging.error(f"Error dropping spotify_url_cache table: {e}")
        logging.error("Traceback:\n" + traceback.format_exc())


def normalize_and_extract_id(url: str) -> tuple[str | None, str | None, str | None]:
    """
    Given a Spotify URL (including possibly a shortened URL),
    return a 3-tuple of (normalized_url, spotify_id, entity_type).
    """
    print(f"[DEBUG] Normalizing URL: {url}")
    if "spotify.link" in url:
        resolved_url = uf.resolve_short_url(url)
        if not resolved_url:
            logging.warning(f"Failed to resolve shortened URL: {url}")
            return None, None, None
        url = resolved_url

    parsed_url = urlparse(url)
    normalized_url = urlunparse(parsed_url._replace(query=""))

    match = re.search(r"spotify\.com/(track|album|artist|show|episode)/([\w\d]+)", normalized_url)
    entity_type = match.group(1) if match else None
    spotify_id = match.group(2) if match else None

    print(f"[DEBUG] Result: normalized_url={normalized_url}, spotify_id={spotify_id}, entity_type={entity_type}")
    return normalized_url, spotify_id, entity_type



def get_cache_data(db_path: str, normalized_url: str) -> pd.DataFrame:
    """
    Retrieve cached data from the 'spotify_url_cache' table for a given normalized URL.

    Args:
        db_path (str): The path to the SQLite database.
        normalized_url (str): The normalized Spotify URL.

    Returns:
        pd.DataFrame: A DataFrame containing matching rows (if any).
    """
    query = "SELECT * FROM spotify_url_cache WHERE normalized_url = ?"
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=(normalized_url,))


def update_cache(
    db_path: str,
    original_url: str,
    normalized_url: str,
    spotify_id: str,
    entity_type: str,
    metadata: dict
) -> None:
    """
    Update or insert the cache with the given URL and metadata information.

    If the normalized_url already exists, we merge the new original_url into 
    the JSON list. Otherwise, we create a new record.

    Args:
        db_path (str): The path to the SQLite database.
        original_url (str): The original (possibly shortened) URL.
        normalized_url (str): The normalized Spotify URL.
        spotify_id (str): The extracted Spotify ID from the URL.
        entity_type (str): Type of spotify entity (track, album, artist, show, episode).
        metadata (dict): Metadata (usually from Spotify API) to be cached.
    """
    existing_data = get_cache_data(db_path, normalized_url)
    if len(existing_data) == 1:
        original_urls = json.loads(existing_data["original_url"].iloc[0])
        if original_url not in original_urls:
            original_urls.append(original_url)
    else:
        original_urls = [original_url]

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO spotify_url_cache (original_url, normalized_url, spotify_id, entity_type, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                json.dumps(original_urls),
                normalized_url,
                spotify_id,
                entity_type,
                json.dumps(metadata),
            ),
        )
        conn.commit()


def is_valid_spotify_id(spotify_id):
    return isinstance(spotify_id, str) and re.fullmatch(r"[A-Za-z0-9]{22}", spotify_id)


def fetch_metadata_in_batches(
    spotify_client: spotipy.Spotify,
    entity_type: str,
    url_triplets: list[tuple[str, str, str]],
) -> list[tuple[dict, str, str, str]]:
    """
    Given a Spotify client, an entity type (track, album, etc.),
    and a list of (original_url, normalized_url, spotify_id) tuples,
    fetch the metadata in batches.

    Args:
        spotify_client (spotipy.Spotify): Authenticated Spotify client.
        entity_type (str): One of 'track', 'album', 'artist', 'show', or 'episode'.
        url_triplets (list[tuple[str, str, str]]): Each tuple is (original_url, normalized_url, spotify_id).

    Returns:
        list[tuple[dict, str, str, str]]:
            Each element is (metadata_item, original_url, normalized_url, spotify_id).
    """
    if not url_triplets:
        return []

    fetch_function_map = {
        "track": spotify_client.tracks,
        "album": spotify_client.albums,
        "artist": spotify_client.artists,
        "show": spotify_client.shows,
        "episode": spotify_client.episodes,
    }
    fetch_function = fetch_function_map.get(entity_type)
    if not fetch_function:
        logging.error(f"Unsupported entity type: {entity_type}")
        return []

    all_metadata = []
    # Different batch sizes for different entity types
    batch_size = 20 if entity_type == "album" else 50

    for batch in uf.batch(url_triplets, batch_size):
        original_urls, normalized_urls, spotify_ids = zip(*batch)
        # Filter for valid Spotify IDs
        valid_indices = [i for i, sid in enumerate(spotify_ids) if is_valid_spotify_id(sid)]
        if not valid_indices:
            continue
        filtered_spotify_ids = [spotify_ids[i] for i in valid_indices]
        filtered_original_urls = [original_urls[i] for i in valid_indices]
        filtered_normalized_urls = [normalized_urls[i] for i in valid_indices]
        try:
            metadata_response = fetch_function(filtered_spotify_ids)
            key_name = entity_type + "s"
            metadata_items = metadata_response.get(key_name, [])
            all_metadata.extend(
                zip(metadata_items, filtered_original_urls, filtered_normalized_urls, filtered_spotify_ids)
            )
        except Exception as e:
            logging.error(f"Error processing batch for entity type '{entity_type}': {e}")
            logging.error("Traceback:\n" + traceback.format_exc())
    return all_metadata


def add_urls_metadata_to_cache_batched(
    spotify_client: spotipy.Spotify,
    input_urls: list[str],
    db_path: str
) -> None:
    start_time = time.time()
    already_cached_count = 0
    new_urls = []

    for url in input_urls:
        normalized_url, spotify_id, entity_type = normalize_and_extract_id(url)
        print(f"[DEBUG] Adding to cache: original_url={url}, normalized_url={normalized_url}, spotify_id={spotify_id}, entity_type={entity_type}")
        if not normalized_url or not spotify_id or not entity_type:
            entity_type = "unsupported"
        cache_data = get_cache_data(db_path, normalized_url)
        if not cache_data.empty:
            already_cached_count += 1
            continue
        new_urls.append((url, normalized_url, spotify_id, entity_type))

    # 2. Group URLs by entity type
    spotify_urls_by_type = {
        "track": [],
        "album": [],
        "artist": [],
        "show": [],
        "episode": [],
        # We explicitly include "unsupported" to store them in the DB too
        "unsupported": [],
    }
    for original_url, normalized_url, spotify_id, entity_type in new_urls:
        if entity_type not in spotify_urls_by_type:
            entity_type = "unsupported"
        spotify_urls_by_type[entity_type].append((original_url, normalized_url, spotify_id))

    # Log quick summary
    total_new = sum(len(urls) for urls in spotify_urls_by_type.values())
    logging.info(f"Skipped {already_cached_count} URLs already in cache.")
    logging.info(f"Found {total_new} new URLs (including unsupported) to be processed.")

    from tqdm import tqdm

    # We'll do two passes:
    #   A) recognized Spotify types -> fetch metadata
    #   B) unsupported -> store with empty metadata

    # A) Recognized Spotify entity types
    recognized_types = ("track", "album", "artist", "show", "episode")
    recognized_count = sum(len(spotify_urls_by_type[t]) for t in recognized_types)
    logging.info(f"Found {recognized_count} new recognized and supported Spotify URLs to be fetched and cached.")

    with tqdm(total=recognized_count, desc="Caching recognized URLs", unit="url") as pbar:
        for et in recognized_types:
            url_triplets = spotify_urls_by_type[et]
            if not url_triplets:
                continue

            results = fetch_metadata_in_batches(spotify_client, et, url_triplets)
            for metadata_item, original_url, normalized_url, spotify_id in results:
                update_cache(
                    db_path=db_path,
                    original_url=original_url,
                    normalized_url=normalized_url,
                    spotify_id=spotify_id,
                    entity_type=et,
                    metadata=metadata_item,
                )
                pbar.update(1)

    # B) Unsupported entity types
    unsupported_triplets = spotify_urls_by_type["unsupported"]
    if unsupported_triplets:
        logging.info(f"Storing {len(unsupported_triplets)} unsupported URLs in cache with empty metadata.")
        for original_url, normalized_url, spotify_id in unsupported_triplets:
            # We store them in the DB but with entity_type="unsupported" and empty metadata
            update_cache(
                db_path=db_path,
                original_url=original_url,
                normalized_url=normalized_url,
                spotify_id=spotify_id,
                entity_type="unsupported",
                metadata={},
            )

    elapsed = time.time() - start_time
    logging.info(f"Completed processing in {elapsed:.2f} seconds.")



def main(df: pd.DataFrame, data_spotify_links_column_name: str, db_path: str | None = None) -> None:
    """
    Main entry point:
    1. Initializes the cache (if not already).
    2. Authenticates with Spotify.
    3. Extracts distinct Spotify links from the given df column.
    4. Adds URL metadata to the cache in batches.

    Args:
        df (pd.DataFrame): A DataFrame that contains a column with Spotify links.
        data_spotify_links_column_name (str): Name of the column containing Spotify links.
        db_path (str | None): Optional path to the SQLite database file.
    """
    logging.info(
"\n" + "-" * 100 + "\n"
"[2] Creating Spotify URL cache and pulling URL metadata using Spotify API\n"
+ "-" * 100
    )

    # 1. Initialize the cache (create table if needed)
    resolved_db_path = initialize_cache(db_path)

    # 2. Authenticate with Spotify
    client_id, client_secret, redirect_uri = get_spotify_credentials()
    spotify_client = authenticate_spotify(client_id, client_secret, redirect_uri, SCOPE)

    # 3. Extract distinct Spotify links from the DataFrame
    logging.info(f"Extracting distinct Spotify links from column '{data_spotify_links_column_name}'.")
    unique_spotify_links = uf.generate_distinct_values_from_list_column(
        df, data_spotify_links_column_name
    )
    logging.info(f"Found {len(unique_spotify_links)} distinct Spotify URLs. Beginning processing now...")

    # 4. Add the URL metadata to cache in batches
    add_urls_metadata_to_cache_batched(spotify_client, unique_spotify_links, resolved_db_path)
