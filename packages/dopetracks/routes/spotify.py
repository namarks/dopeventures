"""
Spotify OAuth and profile endpoints.
"""
import logging
from datetime import datetime, timezone, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database.connection import get_db
from ..database.models import SpotifyToken
from .helpers import _refresh_token_if_needed

logger = logging.getLogger(__name__)

router = APIRouter(tags=["spotify"])


@router.get("/get-client-id")
async def get_client_id():
    """Get Spotify client ID and redirect URI for OAuth."""
    if not settings.SPOTIFY_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")

    if not settings.SPOTIFY_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Spotify redirect URI not configured")

    redirect_uri = settings.SPOTIFY_REDIRECT_URI

    # Validate redirect URI
    if "localhost" in redirect_uri:
        logger.error(f"INVALID redirect URI contains 'localhost': {redirect_uri}")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Redirect URI contains 'localhost'. Spotify requires '127.0.0.1'."
        )

    return {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "redirect_uri": redirect_uri
    }


@router.get("/callback")
async def spotify_callback(
    request: Request,
    code: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    """Handle Spotify OAuth callback."""
    logger.info(f"Callback received - Code: {code is not None}, Error: {error}")

    # Check for OAuth errors from Spotify
    if error:
        logger.error(f"Spotify OAuth error: {error}")
        import html as html_mod
        safe_error = html_mod.escape(error)
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Authorization Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: red; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>Spotify Authorization Failed</h1>
                <p>Error: {safe_error}</p>
                <p><a href="/">Return to app</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=400)

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")

    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET,
    }

    logger.info("Exchanging Spotify authorization code for tokens")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            tokens = response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            try:
                error_json = e.response.json()
                error_detail = error_json.get('error_description', error_json.get('error', error_detail))
            except:
                pass
            logger.error(f"Spotify token exchange failed: {error_detail}")
            raise HTTPException(status_code=400, detail=f"Spotify authorization failed: {error_detail}")
        except httpx.TimeoutException:
            logger.error("Spotify token exchange timed out")
            raise HTTPException(status_code=504, detail="Spotify authorization request timed out")
        except httpx.RequestError as e:
            logger.error(f"Spotify token exchange request error: {e}")
            raise HTTPException(status_code=502, detail=f"Failed to connect to Spotify: {str(e)}")

    # Store tokens locally (no user association)
    expires_at = None
    if tokens.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    # Get or create token entry (only one allowed in local mode)
    token_entry = db.query(SpotifyToken).first()
    if token_entry:
        token_entry.access_token = tokens["access_token"]
        if tokens.get("refresh_token"):
            token_entry.refresh_token = tokens["refresh_token"]
        token_entry.expires_at = expires_at
        token_entry.scope = tokens.get("scope")
        token_entry.updated_at = datetime.now(timezone.utc)
    else:
        token_entry = SpotifyToken(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            expires_at=expires_at,
            scope=tokens.get("scope")
        )
        db.add(token_entry)

    db.commit()
    logger.info("Spotify tokens stored locally")

    # Success page
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spotify Authorization Successful</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .success { color: #1db954; }
        </style>
        <script>
            setTimeout(function() {
                window.location.replace('/');
            }, 1500);
        </script>
    </head>
    <body>
        <div class="success">
            <h1>✅ Spotify Authorization Successful!</h1>
            <p>You can now create Spotify playlists.</p>
            <p>Redirecting to the main app...</p>
            <p><a href="/">Click here if you're not redirected</a></p>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content, status_code=200)


@router.get("/user-profile")
async def get_user_spotify_profile(db: Session = Depends(get_db)):
    """Get user's Spotify profile."""
    token_entry = db.query(SpotifyToken).first()

    if not token_entry:
        raise HTTPException(status_code=401, detail="Spotify not authorized")

    # Refresh token if expired before making the API call
    token_entry = await _refresh_token_if_needed(db, token_entry)

    headers = {"Authorization": f"Bearer {token_entry.access_token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get("https://api.spotify.com/v1/me", headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Invalid Spotify token: {e.response.status_code}")
            raise HTTPException(status_code=401, detail="Invalid Spotify token")
        except httpx.TimeoutException:
            logger.error("Spotify API request timed out")
            raise HTTPException(status_code=504, detail="Spotify API request timed out")
        except httpx.RequestError as e:
            logger.error(f"Spotify API request error: {e}")
            raise HTTPException(status_code=502, detail=f"Failed to connect to Spotify: {str(e)}")


@router.get("/user-playlists")
async def get_user_playlists(db: Session = Depends(get_db)):
    """Get user's Spotify playlists."""
    token_entry = db.query(SpotifyToken).first()

    if not token_entry:
        raise HTTPException(status_code=401, detail="Spotify not authorized")

    import spotipy
    from ..processing.spotify_interaction import create_spotify_playlist as csp

    # Check and refresh token if needed
    token_entry = await _refresh_token_if_needed(db, token_entry)

    sp = spotipy.Spotify(auth=token_entry.access_token)
    user_id = csp.get_user_id(sp)

    playlists = []
    results = sp.user_playlists(user_id, limit=50)

    while results:
        playlists.extend(results['items'])
        if results['next']:
            results = sp.next(results)
        else:
            break

    return {"playlists": playlists}
