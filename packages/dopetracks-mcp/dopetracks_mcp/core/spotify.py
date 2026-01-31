"""
Thin wrapper around existing Spotify functionality.
Handles OAuth with browser flow and token caching.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables from project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)
else:
    # Fallback to default dotenv behavior
    load_dotenv()

# Spotify credentials from environment
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
SCOPE = "playlist-modify-public playlist-modify-private"

# Token cache location
CACHE_DIR = Path.home() / ".dopetracks-mcp"
TOKEN_CACHE_PATH = CACHE_DIR / ".spotify_token_cache"


def _ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_auth_status() -> Dict[str, Any]:
    """
    Check Spotify authentication status.

    Returns dict with: authenticated, user_name, user_id, scopes
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        return {
            "authenticated": False,
            "error": "Spotify credentials not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env",
        }

    _ensure_cache_dir()

    try:
        auth_manager = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=str(TOKEN_CACHE_PATH),
            open_browser=False,
        )

        token_info = auth_manager.get_cached_token()
        if not token_info:
            return {
                "authenticated": False,
                "error": "Not authenticated. Run spotify_login to authenticate.",
            }

        # Validate token by making API call
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.current_user()

        return {
            "authenticated": True,
            "user_name": user.get("display_name"),
            "user_id": user.get("id"),
            "scopes": SCOPE.split(),
        }

    except Exception as e:
        return {
            "authenticated": False,
            "error": f"Authentication check failed: {str(e)}",
        }


def login() -> Dict[str, Any]:
    """
    Initiate Spotify OAuth flow. Opens browser for user authentication.

    Returns dict with: success, message, auth_url (if manual auth needed)
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        return {
            "success": False,
            "error": "Spotify credentials not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env",
        }

    _ensure_cache_dir()

    try:
        auth_manager = SpotifyOAuth(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            redirect_uri=REDIRECT_URI,
            scope=SCOPE,
            cache_path=str(TOKEN_CACHE_PATH),
            open_browser=True,
        )

        # This will open browser and wait for callback
        token_info = auth_manager.get_access_token(as_dict=True)

        if token_info:
            # Verify by getting user info
            sp = spotipy.Spotify(auth_manager=auth_manager)
            user = sp.current_user()

            return {
                "success": True,
                "message": f"Successfully authenticated as {user.get('display_name', user.get('id'))}",
                "user_id": user.get("id"),
            }
        else:
            return {
                "success": False,
                "error": "Failed to get access token",
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Login failed: {str(e)}",
        }


def _get_spotify_client() -> spotipy.Spotify:
    """Get authenticated Spotify client. Raises if not authenticated."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError(
            "Spotify credentials not configured. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env"
        )

    _ensure_cache_dir()

    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(TOKEN_CACHE_PATH),
        open_browser=False,
    )

    token_info = auth_manager.get_cached_token()
    if not token_info:
        raise RuntimeError("Not authenticated with Spotify. Run spotify_login first.")

    return spotipy.Spotify(auth_manager=auth_manager)


def extract_track_id(url: str) -> Optional[str]:
    """Extract Spotify track ID from various URL formats."""
    # Handle spotify.link shortened URLs
    if "spotify.link" in url:
        try:
            import requests
            response = requests.head(url, allow_redirects=True, timeout=5)
            url = response.url
        except Exception:
            return None

    # Extract track ID from open.spotify.com URL
    match = re.search(r"spotify\.com/track/([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)

    return None


def create_playlist(
    name: str,
    track_urls: List[str],
    public: bool = True,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Spotify playlist and add tracks.

    Args:
        name: Playlist name
        track_urls: List of Spotify track URLs
        public: Whether playlist is public
        description: Optional playlist description

    Returns dict with: success, playlist_id, playlist_url, tracks_added, errors
    """
    try:
        sp = _get_spotify_client()
        user_id = sp.current_user()["id"]

        # Extract track IDs from URLs
        track_ids = []
        errors = []
        for url in track_urls:
            track_id = extract_track_id(url)
            if track_id:
                track_ids.append(track_id)
            else:
                errors.append(f"Could not extract track ID from: {url}")

        if not track_ids:
            return {
                "success": False,
                "error": "No valid track IDs found in provided URLs",
                "errors": errors,
            }

        # Deduplicate track IDs
        seen = set()
        unique_track_ids = []
        for tid in track_ids:
            if tid not in seen:
                seen.add(tid)
                unique_track_ids.append(tid)

        # Check if playlist already exists
        playlist = _find_playlist(sp, user_id, name)
        if playlist:
            playlist_id = playlist["id"]
            is_new = False
        else:
            # Create new playlist
            playlist = sp.user_playlist_create(
                user=user_id,
                name=name,
                public=public,
                description=description or f"Created via Dopetracks MCP",
            )
            playlist_id = playlist["id"]
            is_new = True

        # Get existing tracks in playlist
        existing_track_ids = set()
        if not is_new:
            offset = 0
            while True:
                response = sp.playlist_items(
                    playlist_id,
                    limit=100,
                    offset=offset,
                    fields="items.track.id,next",
                )
                for item in response.get("items", []):
                    if item.get("track") and item["track"].get("id"):
                        existing_track_ids.add(item["track"]["id"])
                if not response.get("next"):
                    break
                offset += 100

        # Filter to only new tracks
        new_track_ids = [tid for tid in unique_track_ids if tid not in existing_track_ids]

        # Add tracks in batches of 100
        tracks_added = 0
        for i in range(0, len(new_track_ids), 100):
            batch = new_track_ids[i:i + 100]
            sp.playlist_add_items(playlist_id, batch)
            tracks_added += len(batch)

        playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"

        return {
            "success": True,
            "playlist_id": playlist_id,
            "playlist_url": playlist_url,
            "playlist_name": name,
            "tracks_added": tracks_added,
            "total_tracks": len(existing_track_ids) + tracks_added,
            "skipped_duplicates": len(unique_track_ids) - len(new_track_ids),
            "is_new_playlist": is_new,
            "errors": errors if errors else None,
        }

    except RuntimeError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create playlist: {str(e)}",
        }


def _find_playlist(sp: spotipy.Spotify, user_id: str, name: str) -> Optional[Dict]:
    """Find an existing playlist by name."""
    playlists = sp.user_playlists(user=user_id)
    while playlists:
        for playlist in playlists["items"]:
            if playlist["name"] == name:
                return playlist
        playlists = sp.next(playlists) if playlists["next"] else None
    return None


def get_track_info(track_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Get metadata for Spotify tracks.

    Returns list of track info dicts with: id, name, artist, album, url
    """
    try:
        sp = _get_spotify_client()

        results = []
        # Batch in groups of 50 (Spotify API limit)
        for i in range(0, len(track_ids), 50):
            batch = track_ids[i:i + 50]
            tracks = sp.tracks(batch)

            for track in tracks.get("tracks", []):
                if track:
                    results.append({
                        "id": track["id"],
                        "name": track["name"],
                        "artist": ", ".join(a["name"] for a in track["artists"]),
                        "album": track["album"]["name"],
                        "url": track["external_urls"]["spotify"],
                    })

        return results

    except Exception as e:
        return []
