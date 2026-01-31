"""
MCP tools for Spotify operations.

Tools: spotify_auth_status, spotify_login, create_playlist
"""

from typing import Any, Dict, List, Optional

from ..core import spotify


def spotify_auth_status() -> Dict[str, Any]:
    """
    Check Spotify authentication status.

    Returns:
        Dictionary with:
        - authenticated: Boolean indicating if authenticated
        - user_name: Spotify display name (if authenticated)
        - user_id: Spotify user ID (if authenticated)
        - error: Error message (if not authenticated)

    Example:
        spotify_auth_status() -> {"authenticated": true, "user_name": "John", ...}
    """
    return spotify.get_auth_status()


def spotify_login() -> Dict[str, Any]:
    """
    Initiate Spotify OAuth authentication.

    This will open a browser window for the user to log in to Spotify
    and authorize the application. The token is cached for future use.

    Returns:
        Dictionary with:
        - success: Boolean indicating if login succeeded
        - message: Success or error message
        - user_id: Spotify user ID (if successful)

    Example:
        spotify_login() -> {"success": true, "message": "Authenticated as John"}
    """
    return spotify.login()


def create_playlist(
    name: str,
    track_urls: List[str],
    public: bool = True,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Spotify playlist from a list of track URLs.

    If a playlist with the same name exists, tracks will be added to it
    (duplicates are skipped).

    Args:
        name: Name for the playlist
        track_urls: List of Spotify track URLs (open.spotify.com/track/... or spotify.link/...)
        public: Whether the playlist should be public (default True)
        description: Optional description for the playlist

    Returns:
        Dictionary with:
        - success: Boolean indicating if creation succeeded
        - playlist_url: URL to the created playlist
        - playlist_id: Spotify playlist ID
        - tracks_added: Number of new tracks added
        - total_tracks: Total tracks in playlist
        - is_new_playlist: Whether a new playlist was created
        - errors: Any track URLs that couldn't be processed

    Example:
        create_playlist(
            name="December Vibes",
            track_urls=["https://open.spotify.com/track/abc123", ...]
        )
    """
    return spotify.create_playlist(
        name=name,
        track_urls=track_urls,
        public=public,
        description=description,
    )


def get_track_info(track_urls: List[str]) -> Dict[str, Any]:
    """
    Get metadata for Spotify tracks from their URLs.

    Args:
        track_urls: List of Spotify track URLs

    Returns:
        Dictionary with:
        - tracks: List of track info (id, name, artist, album, url)
        - count: Number of tracks found
        - errors: Any URLs that couldn't be processed

    Example:
        get_track_info(["https://open.spotify.com/track/abc123"])
    """
    try:
        # Extract track IDs from URLs
        track_ids = []
        errors = []
        for url in track_urls:
            track_id = spotify.extract_track_id(url)
            if track_id:
                track_ids.append(track_id)
            else:
                errors.append(f"Could not extract track ID from: {url}")

        if not track_ids:
            return {
                "tracks": [],
                "count": 0,
                "errors": errors,
            }

        tracks = spotify.get_track_info(track_ids)

        return {
            "tracks": tracks,
            "count": len(tracks),
            "errors": errors if errors else None,
        }

    except Exception as e:
        return {
            "error": str(e),
            "tracks": [],
            "count": 0,
        }
