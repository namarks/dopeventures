import sqlite3
import os
import json
import logging
import time
import re
from urllib.parse import urlparse, urlunparse
import requests
import pandas as pd
import dopetracks_summary.utility_functions as uf
import tqdm
import traceback
import spotipy
from spotipy.oauth2 import SpotifyOAuth

CLIENT_ID=os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET=os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI=os.getenv('SPOTIFY_REDIRECT_URI')
SCOPE = "playlist-modify-public playlist-modify-private"


def initialize_spotify_cache(db_path=None):
    if db_path is None:
        cache_dir = os.path.expanduser("~/.spotify_cache")
        os.makedirs(cache_dir, exist_ok=True)
        db_path = os.path.join(cache_dir, "spotify_cache.db")

    conn = sqlite3.connect(db_path)
    return conn

def create_spotify_url_cache_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS spotify_url_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_url TEXT NOT NULL,
            normalized_url TEXT NOT NULL UNIQUE,
            spotify_id TEXT NOT NULL,
            metadata TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return cursor

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

def drop_spotify_url_cache_table(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS spotify_url_cache")
        conn.commit()
        logging.info("spotify_url_cache table dropped successfully.")
    except Exception as e:
        logging.error(f"Error dropping spotify_url_cache table: {e}")
        logging.error("Traceback: " + traceback.format_exc())


def add_urls_metadata_to_cache_batched(spotify_client, input_urls):
    start_time = time.time()

    try:
        conn_cache = initialize_spotify_cache()
        conn_cache.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode
        cursor = create_spotify_url_cache_table(conn_cache)
    except Exception as e:
        logging.error(f"Error initializing cache: {e}")
        logging.error("Traceback: " + traceback.format_exc())
        return None

    try:
        unsupported_urls = []
        new_urls = []
        cached_metadata = []

        for url in tqdm.tqdm(input_urls, desc="Processing URLs", unit="url"):
            original_url = url

            if "spotify.link" in url:
                resolved_url = uf.resolve_short_url(url)
                if not resolved_url:
                    logging.warning(f"Failed to resolve shortened URL: {url}")
                    continue
                url = resolved_url

            if any(x in url for x in ["/wrapped", "/concert", "/playlist", "/socialsession", "/blend"]):
                unsupported_urls.append(original_url)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO spotify_url_cache (original_url, normalized_url, spotify_id, metadata)
                    VALUES (?, ?, ?, ?)
                    """,
                    (json.dumps([original_url]), url, 'Error: unsupported URL', json.dumps({"error": "unsupported URL"}))
                )
                conn_cache.commit()
                continue

            # Normalize the URL
            parsed_url = urlparse(url)
            normalized_url = urlunparse(parsed_url._replace(query=""))

            # Extract Spotify ID from the normalized URL
            match = re.search(r"spotify\.com/(track|album|artist|show|episode)/([\w\d]+)", normalized_url)
            spotify_id = match.group(2) if match else None
            
            if not spotify_id:
                logging.warning(f"Could not extract Spotify ID from URL: {normalized_url}")
                continue

            query = """
                SELECT * FROM spotify_url_cache
                WHERE normalized_url = ?
            """
            existing_cache_data = pd.read_sql_query(query, conn_cache, params=(normalized_url,))
            if len(existing_cache_data) == 1:
                existing_original_urls = json.loads(existing_cache_data['original_url'].iloc[0])
                if original_url not in existing_original_urls:
                    existing_original_urls.append(original_url)
                    cursor.execute(
                        """
                        UPDATE spotify_url_cache
                        SET original_url = ?
                        WHERE normalized_url = ?
                        """,
                        (json.dumps(existing_original_urls), normalized_url)
                    )
                    conn_cache.commit()
                cached_metadata.append(json.loads(existing_cache_data['metadata'].iloc[0]))
            else:
                new_urls.append((original_url, normalized_url, spotify_id))

        if unsupported_urls:
            logging.info(f"Skipped and cached {len(unsupported_urls)} unsupported URLs.")

        if not new_urls:
            logging.info("All URLs were already cached.")

        spotify_urls_by_type = {etype: [] for etype in ["track", "album", "artist", "show", "episode"]}
        for original_url, normalized_url, spotify_id in new_urls:
            match = re.search(r"spotify\.com/(track|album|artist|show|episode)/([\w\d]+)", normalized_url)
            if match:
                entity_type = match.group(1)
                spotify_urls_by_type[entity_type].append((original_url, normalized_url, spotify_id))
            else:
                logging.warning(f"Invalid or unrecognized URL: {original_url}")

        all_metadata = []
        fetch_function_map = {
            "track": spotify_client.tracks,
            "album": spotify_client.albums,
            "artist": spotify_client.artists,
            "show": spotify_client.shows,
            "episode": spotify_client.episodes,
        }

        for entity_type, url_pairs in spotify_urls_by_type.items():
            if not url_pairs:
                logging.debug(f"No URLs to process for {entity_type}")
                continue

            fetch_function = fetch_function_map.get(entity_type)
            if not fetch_function:
                logging.error(f"Unsupported entity type: {entity_type}")
                continue

            batch_size = 20 if entity_type == "album" else 50
            for batch_index, batch in enumerate(tqdm.tqdm(uf.batch(url_pairs, batch_size), desc=f"Processing {entity_type} batches", unit="batch")):
                original_urls, normalized_urls, spotify_ids = zip(*batch)
                logging.info(f"Processing batch {batch_index} of size {len(batch)} for {entity_type}.")

                try:
                    metadata = fetch_function(list(normalized_urls))
                    if not metadata:
                        logging.error(f"Received empty metadata for {entity_type} batch {batch_index}: {normalized_urls}")
                        continue

                    if not isinstance(metadata, dict):
                        logging.error(f"Unexpected metadata format for {entity_type} batch {batch_index}: {metadata}")
                        continue

                    metadata_items = metadata.get(entity_type + "s")
                    if not metadata_items:
                        logging.error(
                            f"Metadata for {entity_type} batch {batch_index} is missing or empty. Batch info: {normalized_urls}, Raw response: {metadata}"
                        )
                        continue
                    
                    for item, original_url, normalized_url, spotify_id in zip(metadata_items, original_urls, normalized_urls, spotify_ids):
                        all_metadata.append((item, original_url, normalized_url, spotify_id))

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        logging.error(f"Resource not found (404) for batch {batch_index}: {normalized_urls}")
                        continue
                except Exception as e:
                    logging.error(f"Unexpected error processing {entity_type} batch {batch_index}: {normalized_urls}. Error: {e}")
                    logging.error("Traceback: " + traceback.format_exc())

        for item, original_url, normalized_url, spotify_id in all_metadata:
            query = """
                SELECT original_url FROM spotify_url_cache
                WHERE normalized_url = ?
            """
            existing_data = pd.read_sql_query(query, conn_cache, params=(normalized_url,))
            if len(existing_data) == 1:
                original_urls = json.loads(existing_data['original_url'].iloc[0])
                if original_url not in original_urls:
                    original_urls.append(original_url)
            else:
                original_urls = [original_url]

            cursor.execute(
                """
                INSERT OR REPLACE INTO spotify_url_cache (original_url, normalized_url, spotify_id, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (json.dumps(original_urls), normalized_url, spotify_id, json.dumps(item))
            )
            conn_cache.commit()

        logging.info(f"Processed {len(all_metadata)} new items.")
    except Exception as e:
        logging.error(f"Error during the caching process: {e}")
        logging.error("Traceback: " + traceback.format_exc())
    finally:
        logging.info(f"Completed in {time.time() - start_time:.2f} seconds.")


def main(df, data_spotify_links_column_name):
    logging.info(
'''
--------------------------------------------------------------------------------------------------------------------
[2] Creating Spotify URL cache and pulling URL metadata using Spotify API
--------------------------------------------------------------------------------------------------------------------
''')
    spotify_client = authenticate_spotify(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SCOPE)
    unique_spotify_links = uf.generate_distinct_values_from_list_column(df, data_spotify_links_column_name)
    add_urls_metadata_to_cache_batched(spotify_client, unique_spotify_links)