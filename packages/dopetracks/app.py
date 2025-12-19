"""
FastAPI application for Dopetracks.
"""
import os
import logging
import sys
import asyncio
import json
import httpx
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

# Add the package to Python path for imports
if __name__ == "__main__":
    package_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(package_path))

from .config import settings
from .database.connection import get_db, init_database, check_database_health
from .database.models import SpotifyToken, LocalCache
from .utils.helpers import get_db_path, validate_db_path
from .services.session_storage import session_storage

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("backend.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Dopetracks Application")
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Check database health
    if not check_database_health():
        logger.error("Database health check failed")
        raise RuntimeError("Database is not accessible")
    
    # Start session storage cleanup task
    session_storage.start_cleanup_task()
    
    logger.info("Application startup complete")
    yield
    
    # Stop session storage cleanup task
    session_storage.stop_cleanup_task()
    
    logger.info("Application shutdown")

# Create FastAPI app
app = FastAPI(
    title="Dopetracks",
    description="Playlist generator from iMessage data",
    version="3.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend)
website_path = Path(__file__).parent.parent.parent / "website"
if website_path.exists():
    # Serve static files (JS, CSS, etc.)
    app.mount("/static", StaticFiles(directory=str(website_path)), name="static")
    
    # Serve individual files directly
    @app.get("/script.js", response_class=Response)
    async def serve_script():
        script_path = website_path / "script.js"
        if script_path.exists():
            return Response(content=script_path.read_text(), media_type="application/javascript")
        raise HTTPException(status_code=404, detail="script.js not found")
    
    @app.get("/config.js", response_class=Response)
    async def serve_config():
        config_path = website_path / "config.js"
        if config_path.exists():
            return Response(content=config_path.read_text(), media_type="application/javascript")
        raise HTTPException(status_code=404, detail="config.js not found")
    
    # Serve index.html at root
    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        index_path = website_path / "index.html"
        if index_path.exists():
            return index_path.read_text()
        return "<h1>Dopetracks Local</h1><p>Frontend not found</p>"

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_healthy = check_database_health()
    db_path = get_db_path()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "messages_db": "found" if db_path else "not_found",
        "messages_db_path": db_path if db_path else None,
        "environment": "local",
        "version": "3.0.0-local"
    }

# Spotify OAuth endpoints
@app.get("/get-client-id")
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

@app.get("/callback")
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
                <h1>❌ Spotify Authorization Failed</h1>
                <p>Error: {error}</p>
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
    from datetime import datetime, timezone, timedelta
    
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

@app.get("/user-profile")
async def get_user_spotify_profile(db: Session = Depends(get_db)):
    """Get user's Spotify profile."""
    token_entry = db.query(SpotifyToken).first()
    
    if not token_entry:
        raise HTTPException(status_code=401, detail="Spotify not authorized")
    
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

@app.get("/user-playlists")
async def get_user_playlists(db: Session = Depends(get_db)):
    """Get user's Spotify playlists."""
    token_entry = db.query(SpotifyToken).first()
    
    if not token_entry:
        raise HTTPException(status_code=401, detail="Spotify not authorized")
    
    import spotipy
    from .processing.spotify_interaction import create_spotify_playlist as csp
    
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

# Helper function to refresh token
async def _refresh_token_if_needed(db: Session, token_entry: SpotifyToken) -> SpotifyToken:
    """Refresh Spotify token if expired."""
    if not token_entry.expires_at:
        return token_entry
    
    # Check if token is expired
    now = datetime.now(timezone.utc)
    expires_at = token_entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if now >= expires_at:
        logger.info("Spotify token expired, refreshing...")
        if not token_entry.refresh_token:
            raise HTTPException(status_code=401, detail="Token expired and no refresh token available")
        
        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token_entry.refresh_token,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(token_url, data=payload)
                response.raise_for_status()
                tokens = response.json()
                token_entry.access_token = tokens["access_token"]
                if tokens.get("refresh_token"):
                    token_entry.refresh_token = tokens["refresh_token"]
                if tokens.get("expires_in"):
                    token_entry.expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
                token_entry.updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("Token refreshed successfully")
            except httpx.HTTPStatusError:
                logger.error("Failed to refresh token: HTTP error")
                raise HTTPException(status_code=401, detail="Failed to refresh token")
            except httpx.TimeoutException:
                logger.error("Token refresh request timed out")
                raise HTTPException(status_code=504, detail="Token refresh request timed out")
            except httpx.RequestError as e:
                logger.error(f"Token refresh request error: {e}")
                raise HTTPException(status_code=502, detail=f"Failed to refresh token: {str(e)}")
    
    return token_entry

# Chat search endpoint
@app.get("/chat-search-optimized")
async def chat_search_optimized(
    query: str,
    db: Session = Depends(get_db)
):
    """Optimized chat search using direct SQL queries."""
    try:
        from .processing.imessage_data_processing.optimized_queries import search_chats_by_name
        
        db_path = get_db_path()
        if not db_path:
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please grant Full Disk Access or specify database path."
            )
        
        if not os.path.exists(db_path):
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )
        
        results = search_chats_by_name(db_path, query)
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )

# Validate database path
@app.get("/validate-username")
async def validate_username(username: str):
    """Validate Messages database path for a username."""
    db_path = f"/Users/{username}/Library/Messages/chat.db"
    
    if validate_db_path(db_path):
        return {
            "valid": True,
            "path": db_path,
            "message": "Database found and accessible"
        }
    else:
        return {
            "valid": False,
            "path": db_path,
            "message": "Database not found or not accessible"
        }

# Playlist creation endpoint (streaming)
@app.post("/create-playlist-optimized-stream")
async def create_playlist_optimized_stream(
    playlist_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    selected_chat_ids: str = Form(...),
    existing_playlist_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Create playlist using optimized direct SQL queries with streaming progress."""
    async def generate_progress():
        try:
            from .processing.imessage_data_processing.optimized_queries import (
                query_messages_with_urls, extract_spotify_urls, extract_all_urls
            )
            from .processing.spotify_interaction import spotify_db_manager as sdm
            from .processing.spotify_interaction import create_spotify_playlist as csp
            from .processing.contacts_data_processing.import_contact_info import get_contact_info_by_handle
            import spotipy
            import pandas as pd
            
            # Parse selected chat IDs
            try:
                chat_ids = json.loads(selected_chat_ids) if selected_chat_ids else []
                chat_ids = [int(cid) for cid in chat_ids]
            except (json.JSONDecodeError, ValueError, TypeError):
                yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid chat selection format'})}\n\n"
                await asyncio.sleep(0)
                return
            
            if not chat_ids:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Please select at least one chat'})}\n\n"
                await asyncio.sleep(0)
                return
            
            # Get database path
            db_path = get_db_path()
            if not db_path:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No Messages database found'})}\n\n"
                await asyncio.sleep(0)
                return
            
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'querying', 'message': f'Querying messages from {len(chat_ids)} chats...', 'progress': 10})}\n\n"
            await asyncio.sleep(0)
            
            # Query messages
            messages_df = query_messages_with_urls(db_path, chat_ids, start_date, end_date)
            
            if messages_df.empty:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No messages found', 'tracks_added': 0, 'track_details': []})}\n\n"
                await asyncio.sleep(0)
                return
            
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'extracting', 'message': f'Found {len(messages_df)} messages. Extracting URLs...', 'progress': 20})}\n\n"
            await asyncio.sleep(0)
            
            # Extract URLs
            text_column = 'final_text' if 'final_text' in messages_df.columns else 'text'
            url_to_message = {}
            skipped_urls = []
            other_links = []
            
            for idx, row in messages_df.iterrows():
                text = row.get(text_column)
                if pd.notna(text) and text:
                    spotify_urls = extract_spotify_urls(str(text))
                    all_urls = extract_all_urls(str(text))
                    
                    # Determine sender and enrich with contact info
                    if bool(row.get('is_from_me', False)):
                        sender_name = "You"
                        sender_full_name = "You"
                        sender_first_name = None
                        sender_last_name = None
                        sender_unique_id = None
                    else:
                        # Get sender contact (phone/email from handle.id, not ROWID)
                        sender_contact = row.get('sender_contact')
                        contact_info = {}
                        
                        # Try to get contact info by sender_contact (phone/email)
                        if pd.notna(sender_contact) and sender_contact:
                            try:
                                contact_info = get_contact_info_by_handle(str(sender_contact)) or {}
                            except Exception as e:
                                logger.debug(f"Error getting contact info for {sender_contact}: {e}")
                                pass
                        
                        # Use contact full name if available, otherwise fall back to phone/email or chat name
                        if contact_info.get("full_name"):
                            sender_name = contact_info["full_name"]
                            sender_full_name = contact_info["full_name"]
                            sender_first_name = contact_info.get("first_name")
                            sender_last_name = contact_info.get("last_name")
                            sender_unique_id = contact_info.get("unique_id")
                        elif pd.notna(sender_contact) and sender_contact:
                            sender_name = str(sender_contact)
                            sender_full_name = str(sender_contact)
                            sender_first_name = None
                            sender_last_name = None
                            sender_unique_id = None
                        else:
                            sender_name = row.get('chat_name', 'Unknown Sender')
                            sender_full_name = sender_name
                            sender_first_name = None
                            sender_last_name = None
                            sender_unique_id = None
                    
                    message_info = {
                        "message_text": str(text),
                        "sender_name": sender_name,
                        "sender_full_name": sender_full_name,
                        "sender_first_name": sender_first_name,
                        "sender_last_name": sender_last_name,
                        "sender_unique_id": sender_unique_id,
                        "is_from_me": bool(row.get('is_from_me', False)),
                        "date": row.get('date_utc', ''),
                        "chat_name": row.get('chat_name', '')
                    }
                    
                    # Process Spotify URLs
                    for url in spotify_urls:
                        _, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                        if '/track/' in url or entity_type == 'track':
                            if url not in url_to_message:
                                url_to_message[url] = {**message_info, "entity_type": entity_type or "track"}
                        else:
                            skipped_info = {
                                "url": url,
                                "entity_type": entity_type or "unknown",
                                "spotify_id": spotify_id,
                                **message_info
                            }
                            skipped_urls.append(skipped_info)
                    
                    # Track non-Spotify links
                    spotify_url_set = set(spotify_urls)
                    for url_info in all_urls:
                        url = url_info["url"]
                        url_type = url_info["type"]
                        if url_type != "spotify" and url not in spotify_url_set:
                            other_link_info = {
                                "url": url,
                                "link_type": url_type,
                                **message_info
                            }
                            other_links.append(other_link_info)
            
            track_urls = list(url_to_message.keys())
            
            if not track_urls:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No Spotify track links found', 'tracks_added': 0, 'total_tracks_found': 0, 'track_details': [], 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                await asyncio.sleep(0)
                return
            
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Found {len(track_urls)} track URLs. Processing tracks...', 'progress': 30})}\n\n"
            await asyncio.sleep(0)
            
            # Get Spotify tokens
            token_entry = db.query(SpotifyToken).first()
            if not token_entry:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Spotify not authorized'})}\n\n"
                await asyncio.sleep(0)
                return
            
            # Refresh token if needed
            token_entry = await _refresh_token_if_needed(db, token_entry)
            
            sp = spotipy.Spotify(auth=token_entry.access_token)
            user_id = csp.get_user_id(sp)
            
            # Get or create playlist
            if existing_playlist_id:
                try:
                    playlist = sp.playlist(existing_playlist_id)
                    logger.info(f"Using existing playlist: {playlist['name']}")
                except:
                    playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
            else:
                playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
            
            # Get existing tracks
            existing_tracks = csp.get_all_playlist_items(sp, playlist['id'])
            existing_track_ids = set(csp.get_song_ids_from_spotify_items(existing_tracks))
            
            # Process tracks
            track_details = []
            track_ids = []
            processed_tracks = 0
            
            for url in track_urls:
                message_info = url_to_message.get(url, {})
                track_info = {
                    "url": url,
                    "track_id": None,
                    "status": "pending",
                    "error": None,
                    "track_name": None,
                    "artist": None,
                    "spotify_url": None,
                    "message_text": message_info.get("message_text", ""),
                    "sender_name": message_info.get("sender_name", "Unknown"),
                    "sender_full_name": message_info.get("sender_full_name"),
                    "sender_first_name": message_info.get("sender_first_name"),
                    "sender_last_name": message_info.get("sender_last_name"),
                    "sender_unique_id": message_info.get("sender_unique_id"),
                    "is_from_me": message_info.get("is_from_me", False),
                    "message_date": message_info.get("date", ""),
                    "chat_name": message_info.get("chat_name", "")
                }
                
                try:
                    _, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                    
                    if entity_type != 'track':
                        track_info["status"] = "skipped"
                        track_info["error"] = f"Not a track (entity type: {entity_type})"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue
                    
                    if not spotify_id:
                        track_info["status"] = "error"
                        track_info["error"] = "Could not extract Spotify ID from URL"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue
                    
                    track_info["track_id"] = spotify_id
                    
                    if not (spotify_id.isalnum() and 15 <= len(spotify_id) <= 22):
                        track_info["status"] = "error"
                        track_info["error"] = f"Invalid ID format"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue
                    
                    if spotify_id in existing_track_ids:
                        track_info["status"] = "skipped"
                        track_info["error"] = "Already in playlist"
                        try:
                            track_data = sp.track(spotify_id)
                            track_info["track_name"] = track_data.get("name", "Unknown")
                            track_info["artist"] = ", ".join([a["name"] for a in track_data.get("artists", [])])
                            track_info["spotify_url"] = track_data.get("external_urls", {}).get("spotify")
                        except:
                            pass
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue
                    
                    # Try to get track data
                    try:
                        track_data = sp.track(spotify_id)
                        track_info["track_name"] = track_data.get("name", "Unknown")
                        track_info["artist"] = ", ".join([a["name"] for a in track_data.get("artists", [])])
                        track_info["spotify_url"] = track_data.get("external_urls", {}).get("spotify")
                        track_info["status"] = "valid"
                        track_ids.append(spotify_id)
                        track_details.append(track_info)
                    except Exception as e:
                        track_info["status"] = "error"
                        error_str = str(e)
                        if "Invalid base62 id" in error_str or "invalid id" in error_str.lower():
                            track_info["error"] = f"Invalid track ID"
                        elif "401" in error_str or "expired" in error_str.lower():
                            track_info["error"] = f"Spotify token expired - please re-authorize"
                        else:
                            error_msg = error_str[:100] if len(error_str) > 100 else error_str
                            track_info["error"] = f"Spotify API error: {error_msg}"
                        track_details.append(track_info)
                        logger.warning(f"Spotify API error for track {spotify_id}: {error_str[:200]}")
                    
                    processed_tracks += 1
                    progress = 30 + int((processed_tracks / len(track_urls)) * 50)
                    yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Processed {processed_tracks}/{len(track_urls)} tracks', 'progress': progress, 'current': processed_tracks, 'total': len(track_urls)})}\n\n"
                    await asyncio.sleep(0)
                    
                except Exception as e:
                    track_info["status"] = "error"
                    track_info["error"] = f"Processing error: {str(e)[:200]}"
                    track_details.append(track_info)
                    processed_tracks += 1
            
            # Add tracks to playlist
            if track_ids:
                yield f"data: {json.dumps({'status': 'progress', 'stage': 'adding', 'message': f'Adding {len(track_ids)} tracks to playlist...', 'progress': 80})}\n\n"
                await asyncio.sleep(0)
                
                try:
                    # Add in batches of 100 (Spotify limit)
                    for i in range(0, len(track_ids), 100):
                        batch = track_ids[i:i+100]
                        sp.playlist_add_items(playlist['id'], batch)
                    
                    yield f"data: {json.dumps({'status': 'complete', 'message': f'Successfully added {len(track_ids)} tracks to playlist', 'tracks_added': len(track_ids), 'total_tracks_found': len(track_urls), 'playlist_id': playlist['id'], 'playlist_name': playlist['name'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                    await asyncio.sleep(0)
                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Failed to add tracks to playlist: {str(e)}', 'tracks_added': 0, 'track_details': track_details})}\n\n"
                    await asyncio.sleep(0)
            else:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No valid tracks to add', 'tracks_added': 0, 'total_tracks_found': len(track_urls), 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                await asyncio.sleep(0)
                
        except Exception as e:
            logger.error(f"Error in playlist creation stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)}'})}\n\n"
            await asyncio.sleep(0)
    
    return StreamingResponse(generate_progress(), media_type="text/event-stream")

# Get recent messages for a chat
@app.get("/chat/{chat_id}/recent-messages")
async def get_recent_messages(chat_id: int, limit: int = 5):
    """Get recent messages for a chat."""
    try:
        from .processing.imessage_data_processing.optimized_queries import get_recent_messages_for_chat
        
        db_path = get_db_path()
        if not db_path:
            raise HTTPException(status_code=400, detail="No Messages database found")
        
        messages = get_recent_messages_for_chat(db_path, chat_id, limit)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Contact photo endpoint
@app.get("/contact-photo/{unique_id}")
async def get_contact_photo(unique_id: str):
    """Get contact photo by unique ID."""
    try:
        import sqlite3
        from pathlib import Path
        from urllib.parse import unquote
        
        # Decode URL-encoded unique_id
        unique_id = unquote(unique_id)
        logger.info(f"Looking for contact photo with unique_id: {unique_id}")
        
        # Find AddressBook database
        sources_dir = Path.home() / "Library/Application Support/AddressBook/Sources"
        if not sources_dir.exists():
            raise HTTPException(status_code=404, detail="AddressBook not found")
        
        # Collect all source directories with databases
        all_source_paths = []
        for folder in sources_dir.iterdir():
            potential_db = folder / "AddressBook-v22.abcddb"
            if potential_db.exists():
                all_source_paths.append(folder)
        
        if not all_source_paths:
            raise HTTPException(status_code=404, detail="AddressBook database not found")
        
        # Helper function to check for external file from UUID reference
        def check_external_file(data_blob, source_path, all_source_paths=None):
            """Check if data_blob is a UUID reference and look for external file."""
            if not data_blob or len(data_blob) >= 100:
                return None
            try:
                # Strip leading non-printable bytes (like \x00, \x01, \x02, etc.)
                # Try to decode, but handle binary data that might have leading bytes
                uuid_ref = data_blob.decode('utf-8', errors='ignore')
                # Strip common leading bytes and whitespace
                uuid_ref = uuid_ref.lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')
                uuid_ref = uuid_ref.strip('\x00').strip()
                logger.debug(f"Decoded UUID reference: {uuid_ref!r} (length: {len(uuid_ref)}, original blob length: {len(data_blob)})")
                # Check if it looks like a UUID (has dashes and is reasonable length)
                if '-' in uuid_ref and len(uuid_ref) > 30:
                    # First try the current source directory
                    search_paths = [source_path]
                    # If provided, also search other source directories
                    if all_source_paths:
                        search_paths.extend([sp for sp in all_source_paths if sp != source_path])
                    
                    logger.debug(f"Searching for external file in {len(search_paths)} directories")
                    for search_path in search_paths:
                        external_data_dir = search_path / ".AddressBook-v22_SUPPORT" / "_EXTERNAL_DATA"
                        external_file = external_data_dir / uuid_ref
                        logger.debug(f"Checking: {external_file} (exists: {external_file.exists()})")
                        if external_file.exists():
                            # Read the external file
                            external_image = external_file.read_bytes()
                            if len(external_image) > 100:
                                logger.info(f"Found shared photo in external data: {external_file} (UUID: {uuid_ref}, size: {len(external_image)} bytes)")
                                return external_image
                            else:
                                logger.debug(f"External file too small at: {external_file} ({len(external_image)} bytes)")
                        else:
                            logger.debug(f"External file not found at: {external_file}")
                else:
                    logger.debug(f"Data doesn't look like a UUID reference (length: {len(uuid_ref)}, has dashes: {'-' in uuid_ref})")
            except Exception as e:
                logger.debug(f"Could not parse as UUID reference: {e}", exc_info=True)
            return None
        
        # Helper function to process and return image data
        def process_and_return_image(image_data, unique_id):
            """Process image data and return HTTP response."""
            if not image_data or len(image_data) < 100:
                return None
            
            # Some images may have extra bytes at the start (like \x01)
            # Check for leading non-image bytes
            if image_data[:1] == b'\x01' and image_data[1:4] in [b'\x89PN', b'\xff\xd8\xff']:
                image_data = image_data[1:]
            
            # Detect format
            if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = 'image/png'
            elif image_data[:4] == b'\x89PNG':
                media_type = 'image/png'
            elif image_data[:3] == b'\xff\xd8\xff':
                media_type = 'image/jpeg'
            elif image_data[:4] == b'II*\x00' or image_data[:4] == b'MM\x00*':
                media_type = 'image/tiff'
            else:
                # Unknown format, try to detect from first few bytes
                logger.warning(f"Unknown image format for unique_id: {unique_id}, first bytes: {image_data[:10].hex()}")
                media_type = 'image/jpeg'
            
            logger.info(f"Found contact photo for unique_id: {unique_id}, size: {len(image_data)} bytes, type: {media_type}")
            return Response(content=image_data, media_type=media_type)
        
        # Search through all source directories
        for source_path in all_source_paths:
            db_path = source_path / "AddressBook-v22.abcddb"
            
            # Query for photo
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Try with and without :ABPerson suffix
            for uid_variant in [unique_id, unique_id.replace(':ABPerson', ''), unique_id + ':ABPerson']:
                cursor.execute("""
                    SELECT ZIMAGEDATA, ZTHUMBNAILIMAGEDATA 
                    FROM ZABCDRECORD 
                    WHERE ZUNIQUEID = ?
                """, (uid_variant,))
                
                row = cursor.fetchone()
                if row:
                    logger.debug(f"Found row in database {db_path} for unique_id variant: {uid_variant}")
                    image_data = row[0]
                    thumbnail_data = row[1]
                    
                    logger.debug(f"Image data: {len(image_data) if image_data else 0} bytes, Thumbnail: {len(thumbnail_data) if thumbnail_data else 0} bytes")
                    
                    # Check ZIMAGEDATA (full image)
                    if image_data:
                        if len(image_data) > 100:
                            # Actual image data
                            logger.debug(f"Found full image data ({len(image_data)} bytes)")
                            result = process_and_return_image(image_data, unique_id)
                            if result:
                                conn.close()
                                return result
                        else:
                            # Might be a UUID reference - check external file
                            logger.debug(f"Image data is small ({len(image_data)} bytes), checking for UUID reference")
                            external_image = check_external_file(image_data, source_path, all_source_paths)
                            if external_image:
                                logger.info(f"Found external image file for unique_id: {unique_id}")
                                result = process_and_return_image(external_image, unique_id)
                                if result:
                                    conn.close()
                                    return result
                            else:
                                logger.debug(f"No external file found for small image data")
                    else:
                        logger.debug(f"No image data in ZIMAGEDATA column")
                    
                    # If no full image, check thumbnail
                    if thumbnail_data:
                        if len(thumbnail_data) > 100:
                            # Actual image data
                            logger.debug(f"Found thumbnail image data ({len(thumbnail_data)} bytes)")
                            result = process_and_return_image(thumbnail_data, unique_id)
                            if result:
                                conn.close()
                                return result
                        else:
                            # Might be a UUID reference - check external file
                            logger.debug(f"Thumbnail data is small ({len(thumbnail_data)} bytes), checking for UUID reference")
                            external_image = check_external_file(thumbnail_data, source_path, all_source_paths)
                            if external_image:
                                logger.info(f"Found external thumbnail file for unique_id: {unique_id}")
                                result = process_and_return_image(external_image, unique_id)
                                if result:
                                    conn.close()
                                    return result
                            else:
                                logger.debug(f"No external file found for small thumbnail data")
                    else:
                        logger.debug(f"No thumbnail data in ZTHUMBNAILIMAGEDATA column")
                else:
                    logger.debug(f"No row found in database {db_path} for unique_id variant: {uid_variant}")
            
            conn.close()
        
        # Return 404 if photo not found
        logger.warning(f"Contact photo not found for unique_id: {unique_id}")
        raise HTTPException(status_code=404, detail=f"Photo not found for unique_id: {unique_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug/contact/{name}")
async def debug_contact(name: str):
    """Debug endpoint to find contact info by name."""
    try:
        import sqlite3
        from pathlib import Path
        
        sources_dir = Path.home() / "Library/Application Support/AddressBook/Sources"
        if not sources_dir.exists():
            return {"error": "AddressBook Sources directory not found"}
        
        results = []
        for folder in sources_dir.iterdir():
            potential_db = folder / "AddressBook-v22.abcddb"
            if potential_db.exists():
                conn = sqlite3.connect(str(potential_db))
                cursor = conn.cursor()
                
                # Search for contact by name
                cursor.execute("""
                    SELECT ZFIRSTNAME, ZLASTNAME, ZUNIQUEID, 
                           LENGTH(ZIMAGEDATA) as image_size,
                           LENGTH(ZTHUMBNAILIMAGEDATA) as thumbnail_size,
                           CASE 
                               WHEN LENGTH(ZTHUMBNAILIMAGEDATA) < 100 THEN ZTHUMBNAILIMAGEDATA
                               ELSE NULL
                           END as thumbnail_preview
                    FROM ZABCDRECORD
                    WHERE (ZFIRSTNAME LIKE ? OR ZLASTNAME LIKE ? OR (ZFIRSTNAME || ' ' || ZLASTNAME) LIKE ?)
                    LIMIT 10
                """, (f'%{name}%', f'%{name}%', f'%{name}%'))
                
                rows = cursor.fetchall()
                for row in rows:
                    first_name, last_name, unique_id, image_size, thumbnail_size, thumbnail_preview = row
                    full_name = f"{first_name or ''} {last_name or ''}".strip()
                    
                    # Check if thumbnail is a UUID reference
                    uuid_ref = None
                    if thumbnail_preview and len(thumbnail_preview) < 100:
                        try:
                            uuid_ref = thumbnail_preview.decode('utf-8', errors='ignore')
                            # Strip leading non-printable bytes
                            uuid_ref = uuid_ref.lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')
                            uuid_ref = uuid_ref.strip('\x00').strip()
                        except:
                            pass
                    
                    # Check for external file
                    external_file_exists = False
                    if uuid_ref and '-' in uuid_ref and len(uuid_ref) > 30:
                        external_data_dir = folder / ".AddressBook-v22_SUPPORT" / "_EXTERNAL_DATA"
                        external_file = external_data_dir / uuid_ref
                        external_file_exists = external_file.exists()
                        # Also check if the directory exists
                        if not external_file_exists and external_data_dir.exists():
                            # List files in the directory to see what's there
                            logger.debug(f"External data dir exists but file not found. Dir: {external_data_dir}")
                    
                    results.append({
                        "full_name": full_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "unique_id": unique_id,
                        "image_size": image_size or 0,
                        "thumbnail_size": thumbnail_size or 0,
                        "thumbnail_is_uuid": uuid_ref is not None and '-' in uuid_ref and len(uuid_ref) > 30,
                        "uuid_reference": uuid_ref if uuid_ref and '-' in uuid_ref and len(uuid_ref) > 30 else None,
                        "external_file_exists": external_file_exists,
                        "source_folder": str(folder)
                    })
                
                conn.close()
        
        return {
            "search_name": name,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error in debug contact: {e}", exc_info=True)
        return {"error": str(e)}
