"""
FastAPI application for Dopetracks.
"""
import os
import logging
import sys
import asyncio
import json
import httpx
import queue
import time
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

# Add the package to Python path for imports
if __name__ == "__main__":
    package_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(package_path))

from .config import settings
from .database.connection import get_db, init_database, check_database_health
from .database.models import SpotifyToken
from .utils.helpers import get_db_path, validate_db_path
from .utils import dictionaries
from .processing.imessage_data_processing.prepared_messages import (
    chat_search_prepared,
    get_last_processed_date,
)
from .processing.contacts_data_processing.import_contact_info import (
    get_contact_info_by_handle,
)
from .processing.imessage_data_processing.handle_utils import (
    normalize_handle,
    normalize_handle_variants,
)
from .processing.imessage_data_processing.optimized_queries import (
    advanced_chat_search,
    advanced_chat_search_streaming,
)
from .processing.imessage_data_processing.ingestion import ingest_prepared_store, get_source_max_date

# Determine log file path (use proper directory for bundled apps)
if getattr(sys, 'frozen', False):
    # Bundled app - use user log directory
    log_dir = Path.home() / 'Library' / 'Logs' / 'Dopetracks'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'backend.log'
else:
    # Development - use project root or user log directory
    # Try to find project root first
    project_root = Path(__file__).parent.parent.parent.parent
    if (project_root / "packages" / "dopetracks").exists():
        # We're in the project structure
        log_file = project_root / "backend.log"
    else:
        # Fallback to user log directory
        log_dir = Path.home() / 'Library' / 'Logs' / 'Dopetracks'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'backend.log'
    
    # Ensure parent directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Simple in-memory TTL cache for chat list
CHAT_CACHE_TTL_SECONDS = 30
_chat_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
# Path to prepared DB (populated via ingestion)
PREPARED_DB_PATH: Optional[str] = None
PREPARED_STATUS: Dict[str, Any] = {
    "last_prepared_date": None,
    "source_max_date": None,
    "staleness_seconds": None,
    "last_check_ts": None,
}


def _refresh_prepared_db(source_db_path: str, force_rebuild: bool = False) -> Optional[str]:
    """Run incremental ingestion and update global prepared DB path."""
    global PREPARED_DB_PATH, _chat_cache
    result = ingest_prepared_store(
        source_db_path=source_db_path,
        base_dir=None,
        force_rebuild=force_rebuild,
    )
    prepared_db_path = result.get("prepared_db_path")
    if prepared_db_path and prepared_db_path != PREPARED_DB_PATH:
        _chat_cache.clear()
    if prepared_db_path:
        PREPARED_DB_PATH = prepared_db_path
    return PREPARED_DB_PATH


def _parse_naive_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str or dt_str == "0":
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None


def _compute_staleness_seconds(source_dt: Optional[str], prepared_dt: Optional[str]) -> Optional[int]:
    src = _parse_naive_dt(source_dt)
    prep = _parse_naive_dt(prepared_dt)
    if not src or not prep:
        return None
    delta = (src - prep).total_seconds()
    return int(delta) if delta > 0 else 0


def _resolve_sender_name_from_prepared(prepared_db: str, sender_handle: Optional[str]) -> Optional[Dict[str, Any]]:
    if not sender_handle:
        return None
    variants = normalize_handle_variants(sender_handle)
    if not variants:
        return None
    try:
        conn = sqlite3.connect(prepared_db)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(variants))
        cur.execute(
            f"""
            SELECT contact_info, display_name
            FROM contacts
            WHERE contact_info IN ({placeholders})
            LIMIT 1
            """,
            variants,
        )
        row = cur.fetchone()
        conn.close()
        if row:
            contact_info, display_name = row
            return {
                "full_name": display_name or contact_info,
                "first_name": None,
                "last_name": None,
            }
    except Exception:
        return None
    return None


def _lookup_prepared_contact(prepared_db: str, handle: str) -> Optional[str]:
    """Lookup display name in prepared contacts table using normalized variants."""
    variants = normalize_handle_variants(handle)
    if not variants:
        return None
    try:
        conn = sqlite3.connect(prepared_db)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(variants))
        cur.execute(
            f"SELECT display_name FROM contacts WHERE contact_info IN ({placeholders}) LIMIT 1",
            variants,
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        return None
    return None


def _resolve_handle_display(prepared_db: Optional[str], handle: Optional[str]) -> Optional[str]:
    """Resolve a handle to display name using prepared contacts then AddressBook with variants."""
    if not handle:
        return None
    variants = normalize_handle_variants(handle)
    if prepared_db:
        name = _lookup_prepared_contact(prepared_db, handle)
        if name:
            return name
        # If not found on raw, try other variants explicitly
        if len(variants) > 1:
            try:
                conn = sqlite3.connect(prepared_db)
                cur = conn.cursor()
                placeholders = ",".join("?" * len(variants))
                cur.execute(
                    f"SELECT display_name FROM contacts WHERE contact_info IN ({placeholders}) LIMIT 1",
                    variants,
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
    # AddressBook fallback with variants
    for v in variants:
        try:
            info = get_contact_info_by_handle(v)
            if info and info.get("full_name"):
                return info["full_name"]
        except Exception:
            continue
    return None


def _build_participant_name_map(source_db: str, prepared_db: Optional[str], chat_ids: List[int]) -> Dict[str, str]:
    """Resolve participant handles to names using prepared contacts then AddressBook."""
    if not chat_ids:
        return {}
    mapping: Dict[str, str] = {}
    placeholders = ",".join(["?"] * len(chat_ids))
    try:
        conn = sqlite3.connect(source_db)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT DISTINCT h.id
            FROM chat_handle_join chj
            JOIN handle h ON chj.handle_id = h.ROWID
            WHERE chj.chat_id IN ({placeholders})
            """,
            chat_ids,
        )
        handles = [r[0] for r in cur.fetchall() if r and r[0]]
        conn.close()
    except Exception:
        handles = []

    for raw_handle in handles:
        display = _resolve_handle_display(prepared_db, raw_handle)
        if display:
            for v in normalize_handle_variants(raw_handle):
                mapping[v] = display
    return mapping


def _find_equivalent_chat_ids(chat_id: int, source_db_path: str) -> Optional[List[int]]:
    """
    Find other chat_ids with identical participant sets (using source chat.db).
    Returns None on error to fall back to the single chat_id.
    """
    try:
        conn = sqlite3.connect(source_db_path)
        try:
            cur = conn.cursor()
            # Get participant handles for the target chat
            cur.execute(
                """
                SELECT h.id
                FROM chat_handle_join chj
                JOIN handle h ON chj.handle_id = h.ROWID
                WHERE chj.chat_id = ?
                """,
                (chat_id,),
            )
            handles = [normalize_handle(r[0]) for r in cur.fetchall() if r and r[0]]
            handles = [h for h in handles if h]
            if not handles:
                return None
            handle_set = set(handles)

            # Find other chats with exactly this participant set
            placeholders = ",".join("?" * len(handle_set))
            # Chats whose participant count matches and whose handles set matches
            cur.execute(
                f"""
                WITH ch_participants AS (
                    SELECT chj.chat_id, GROUP_CONCAT(DISTINCT h.id) AS handles_raw
                    FROM chat_handle_join chj
                    JOIN handle h ON chj.handle_id = h.ROWID
                    GROUP BY chj.chat_id
                )
                SELECT chat_id
                FROM ch_participants
                WHERE chat_id IN (
                    SELECT chat_id FROM chat_handle_join GROUP BY chat_id HAVING COUNT(DISTINCT handle_id)=?
                )
                """,
                (len(handle_set),),
            )
            candidate_ids = [int(r[0]) for r in cur.fetchall()]
            if not candidate_ids:
                return [chat_id]

            # Fetch handles for candidates and match sets
            matches: List[int] = []
            for cid in candidate_ids:
                cur.execute(
                    """
                    SELECT h.id
                    FROM chat_handle_join chj
                    JOIN handle h ON chj.handle_id = h.ROWID
                    WHERE chj.chat_id = ?
                    """,
                    (cid,),
                )
                ch_handles = [normalize_handle(r[0]) for r in cur.fetchall() if r and r[0]]
                ch_handles = [h for h in ch_handles if h]
                if set(ch_handles) == handle_set:
                    matches.append(cid)

            return matches or [chat_id]
        finally:
            conn.close()
    except Exception:
        return None

# FTS indexer imports
try:
    from .processing.imessage_data_processing.fts_indexer import (
        get_fts_db_path,
        populate_fts_database,
        get_fts_status,
        is_fts_available
    )
    FTS_AVAILABLE = True
except ImportError:
    FTS_AVAILABLE = False
    logger.warning("FTS indexer not available - will use fallback search method")


async def _periodic_prepared_refresh(interval_seconds: int = 300):
    """Background refresher that keeps prepared DB in sync and tracks staleness."""
    global PREPARED_STATUS
    while True:
        try:
            db_path = get_db_path()
            if not db_path or not os.path.exists(db_path):
                PREPARED_STATUS = {
                    "last_prepared_date": None,
                    "source_max_date": None,
                    "staleness_seconds": None,
                    "last_check_ts": time.time(),
                }
            else:
                loop = asyncio.get_event_loop()
                source_max_date = await loop.run_in_executor(None, get_source_max_date, db_path)

                prepared_path = PREPARED_DB_PATH
                prepared_date = None
                if prepared_path and os.path.exists(prepared_path):
                    prepared_date = get_last_processed_date(Path(prepared_path))

                needs_refresh = False
                if source_max_date and prepared_date:
                    needs_refresh = source_max_date > prepared_date
                elif source_max_date and not prepared_date:
                    needs_refresh = True

                if needs_refresh:
                    await loop.run_in_executor(None, _refresh_prepared_db, db_path)
                    prepared_path = PREPARED_DB_PATH
                    if prepared_path and os.path.exists(prepared_path):
                        prepared_date = get_last_processed_date(Path(prepared_path))

                staleness = _compute_staleness_seconds(source_max_date, prepared_date)
                PREPARED_STATUS = {
                    "last_prepared_date": prepared_date,
                    "source_max_date": source_max_date,
                    "staleness_seconds": staleness,
                    "last_check_ts": time.time(),
                }
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Prepared DB refresh loop error: {exc}", exc_info=True)
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Dopetracks Application")
    
    # Initialize database asynchronously (non-blocking)
    # This allows the app to start serving requests while DB initializes
    async def init_db_async():
        """Initialize database in background."""
        try:
            # Run blocking DB init in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, init_database)
            logger.info("Database initialized successfully")
            
            # Check database health
            health_ok = await loop.run_in_executor(None, check_database_health)
            if not health_ok:
                logger.error("Database health check failed")
                raise RuntimeError("Database is not accessible")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            # Don't raise - allow app to start, but endpoints will handle errors
    
    # Start database initialization in background
    db_init_task = asyncio.create_task(init_db_async())
    prepared_refresh_task = asyncio.create_task(_periodic_prepared_refresh(300))
    
    # Prepare messages database (incremental)
    try:
        db_path = get_db_path()
        if db_path and os.path.exists(db_path):
            prepared_db = _refresh_prepared_db(db_path)
            if prepared_db:
                logger.info(f"Prepared DB ready at {prepared_db}")
            else:
                logger.warning("Prepared DB update skipped: ingestion returned no path.")
        else:
            logger.warning("Prepared DB update skipped: Messages database not found or inaccessible.")
    except Exception as e:
        logger.error(f"Error updating prepared DB: {e}", exc_info=True)
    
    logger.info("Application startup complete (database initializing in background)")
    yield
    
    # Wait for DB init to complete (if still running)
    try:
        await db_init_task
    except Exception as e:
        logger.warning(f"Database initialization had errors: {e}")
    # Stop prepared refresh loop
    try:
        prepared_refresh_task.cancel()
        await prepared_refresh_task
    except Exception:
        pass
    
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

# Root endpoint - API info for native app
@app.get("/")
async def read_root():
    """API root endpoint - returns API information."""
    return {
        "name": "Dopetracks API",
        "version": "3.0.0",
        "description": "Playlist generator from iMessage data - Native macOS App",
        "docs": "/docs",
        "health": "/health"
    }

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


@app.get("/prepared-status")
async def prepared_status():
    """Return staleness info for the prepared DB."""
    return {
        "prepared_db_path": PREPARED_DB_PATH,
        "last_prepared_date": PREPARED_STATUS.get("last_prepared_date"),
        "source_max_date": PREPARED_STATUS.get("source_max_date"),
        "staleness_seconds": PREPARED_STATUS.get("staleness_seconds"),
        "last_check_ts": PREPARED_STATUS.get("last_check_ts"),
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

# Get all chats endpoint
@app.get("/chats")
async def get_all_chats(db: Session = Depends(get_db)):
    """Get all chats with basic statistics."""
    try:
        from .processing.imessage_data_processing.optimized_queries import get_chat_list
        start_time = time.perf_counter()
        
        db_path = get_db_path()
        if not db_path:
            logger.error("get_all_chats: get_db_path() returned None - check logs for details")
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please grant Full Disk Access in System Preferences > Security & Privacy > Privacy > Full Disk Access, or upload your Messages database file manually."
            )
        
        if not os.path.exists(db_path):
            logger.error(f"get_all_chats: Database path does not exist: {db_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )
        
        # Refresh prepared DB incrementally
        prepared_db = _refresh_prepared_db(db_path)

        now = time.monotonic()
        cache_key = f"{db_path}|{prepared_db or ''}"
        cache_entry = _chat_cache.get(cache_key)
        if cache_entry:
            ts, cached = cache_entry
            if now - ts < CHAT_CACHE_TTL_SECONDS:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"get_all_chats: Served {len(cached)} chats from cache in {elapsed_ms:.0f} ms (TTL {CHAT_CACHE_TTL_SECONDS}s)")
                return cached
        
        logger.info(f"get_all_chats: Loading all chats from database {db_path}")
        results = get_chat_list(db_path, prepared_db_path=prepared_db)
        _chat_cache[cache_key] = (now, results)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"get_all_chats: Found {len(results)} chats in {elapsed_ms:.0f} ms (cached for {CHAT_CACHE_TTL_SECONDS}s)")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all chats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading chats: {str(e)}"
        )

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
            logger.error("chat_search_optimized: get_db_path() returned None - check logs for details")
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please grant Full Disk Access in System Preferences > Security & Privacy > Privacy > Full Disk Access, or upload your Messages database file manually."
            )
        
        if not os.path.exists(db_path):
            logger.error(f"chat_search_optimized: Database path does not exist: {db_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )
        
        logger.info(f"chat_search_optimized: Searching chats with query '{query}' in database {db_path}")
        results = search_chats_by_name(db_path, query)
        logger.info(f"chat_search_optimized: Found {len(results)} results")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )

# Prepared chat search (uses prepared_messages.db)
@app.get("/chat-search-prepared")
async def chat_search_prepared_endpoint(
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[str] = None,  # currently unused in prepared search
    message_content: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")
        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db:
            raise HTTPException(status_code=500, detail="Failed to prepare messages database")
        
        participant_list = None
        if participant_names:
            participant_list = [name.strip() for name in participant_names.split(',') if name.strip()]
        
        results = chat_search_prepared(
            prepared_db,
            query,
            start_date,
            end_date,
            participant_list,
            message_content,
            limit_to_recent=5000
        )
        logger.info(f"chat_search_prepared: Found {len(results)} results")
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_search_prepared: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Advanced chat search endpoint (streaming)
@app.get("/chat-search-advanced")
async def chat_search_advanced(
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[str] = None,  # Comma-separated list
    message_content: Optional[str] = None,
    stream: bool = False,  # Enable streaming mode
    db: Session = Depends(get_db)
):
    """Advanced chat search with multiple filter criteria. Supports streaming results."""
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")

        # Keep prepared DB up-to-date and reuse it for message-content filtering
        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db or not os.path.exists(prepared_db):
            logger.error("chat_search_advanced: prepared DB not found")
            raise HTTPException(
                status_code=500,
                detail="Prepared messages database not found. Please retry startup."
            )
        
        # Parse participant names (comma-separated)
        participant_list = None
        if participant_names:
            participant_list = [name.strip() for name in participant_names.split(',') if name.strip()]
        
        logger.info(f"chat_search_advanced: Searching with query='{query}', start_date='{start_date}', end_date='{end_date}', participants={participant_list}, message_content='{message_content}', stream={stream}")
        
        if stream:
            # Streaming mode: yield results as they're found
            async def generate_results():
                loop = asyncio.get_event_loop()
                try:
                    # Create a queue to pass results from thread to async generator
                    result_queue = queue.Queue()
                    exception_queue = queue.Queue()
                    
                    def run_search():
                        try:
                            result_count = 0
                            for result in advanced_chat_search_streaming(
                                db_path=source_db,
                                query=query,
                                start_date=start_date,
                                end_date=end_date,
                                participant_names=participant_list,
                                message_content=message_content,
                                limit_to_recent=None,
                                prepared_db_path=prepared_db,
                            ):
                                result_count += 1
                                result_queue.put(result)
                            logger.info(f"Streaming search completed: {result_count} results found")
                            result_queue.put(None)  # Sentinel to signal completion
                        except Exception as e:
                            logger.error(f"Error in run_search: {e}", exc_info=True)
                            exception_queue.put(e)
                            # Also put sentinel to signal completion even on error
                            try:
                                result_queue.put(None)
                            except:
                                pass
                    
                    # Start search in thread pool with timeout
                    search_task = loop.run_in_executor(None, run_search)
                    
                    # Yield results as they arrive (with overall timeout)
                    timeout_seconds = 300  # 5 minutes max for streaming search
                    start_time = time.time()
                    
                    while True:
                        # Check for timeout
                        elapsed = time.time() - start_time
                        if elapsed > timeout_seconds:
                            logger.warning(f"Streaming search timed out after {timeout_seconds} seconds")
                            search_task.cancel()
                            yield f"data: {json.dumps({'status': 'error', 'message': f'Search timed out after {timeout_seconds} seconds'})}\n\n"
                            break
                        # Check for exceptions
                        try:
                            exc = exception_queue.get_nowait()
                            raise exc
                        except queue.Empty:
                            pass
                        
                        # Check for results
                        try:
                            result = result_queue.get(timeout=0.1)
                            if result is None:  # Completion sentinel
                                break
                            yield f"data: {json.dumps(result)}\n\n"
                            await asyncio.sleep(0)  # Yield to event loop
                        except queue.Empty:
                            # Check if search task is done
                            if search_task.done():
                                # Process any remaining results
                                while True:
                                    try:
                                        result = result_queue.get_nowait()
                                        if result is None:
                                            break
                                        yield f"data: {json.dumps(result)}\n\n"
                                        await asyncio.sleep(0)
                                    except queue.Empty:
                                        break
                                break
                            await asyncio.sleep(0.01)  # Small delay before checking again
                    
                    yield f"data: {json.dumps({'status': 'complete'})}\n\n"
                except Exception as e:
                    logger.error(f"Error in streaming search: {e}", exc_info=True)
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
            
            return StreamingResponse(
                generate_results(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Non-streaming mode: return all results at once
            loop = asyncio.get_event_loop()
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: list(
                            advanced_chat_search(
                                db_path=source_db,
                                query=query,
                                start_date=start_date,
                                end_date=end_date,
                                participant_names=participant_list,
                                message_content=message_content,
                                limit_to_recent=None,
                                prepared_db_path=prepared_db,
                            )
                        ),
                    ),
                    timeout=120.0
                )
                logger.info(f"chat_search_advanced: Found {len(results)} results")
                return results
            except asyncio.TimeoutError:
                logger.error("chat_search_advanced: Search operation timed out after 120 seconds")
                raise HTTPException(
                    status_code=504,
                    detail="Search operation timed out. Try narrowing your search criteria (date range, participants, or message content)."
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )

@app.post("/fts/index")
async def index_fts_database(
    force_rebuild: bool = False,
    db: Session = Depends(get_db)
):
    """Create or update FTS index for Messages database."""
    if not FTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="FTS indexer not available"
        )
    
    try:
        db_path = get_db_path()
        if not db_path or not os.path.exists(db_path):
            raise HTTPException(
                status_code=404,
                detail="Messages database not found"
            )
        
        fts_db_path = get_fts_db_path(db_path)
        
        logger.info(f"Starting FTS indexing for {db_path} (force_rebuild={force_rebuild})")
        
        # Run indexing in executor to avoid blocking
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(
            None,
            lambda: populate_fts_database(
                fts_db_path=fts_db_path,
                source_db_path=db_path,
                batch_size=1000,
                force_rebuild=force_rebuild
            )
        )
        
        return {
            "status": "success",
            "fts_db_path": fts_db_path,
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FTS indexing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fts/status")
async def get_fts_index_status(db: Session = Depends(get_db)):
    """Get status of FTS index."""
    if not FTS_AVAILABLE:
        return {"available": False, "reason": "FTS indexer not available"}
    
    try:
        db_path = get_db_path()
        if not db_path:
            return {"available": False, "reason": "No database path"}
        
        fts_db_path = get_fts_db_path(db_path)
        available = is_fts_available(fts_db_path)
        
        if available:
            status = get_fts_status(fts_db_path)
            return {
                "available": True,
                "fts_db_path": fts_db_path,
                "status": status
            }
        else:
            return {
                "available": False,
                "fts_db_path": fts_db_path,
                "reason": "FTS database not found or empty"
            }
            
    except Exception as e:
        logger.error(f"Error getting FTS status: {e}")
        return {"available": False, "error": str(e)}

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

# Open System Settings to Full Disk Access
@app.get("/open-full-disk-access")
async def open_full_disk_access():
    """Open macOS System Settings to Full Disk Access section."""
    import subprocess
    import platform
    
    if platform.system() != "Darwin":
        raise HTTPException(status_code=400, detail="This feature is only available on macOS")
    
    try:
        # Open System Settings to Full Disk Access
        # For macOS Ventura+ (13.0+), use the new URL scheme
        # For older macOS, use the old System Preferences path
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
        ], check=True)
        return {"success": True, "message": "Opening System Settings to Full Disk Access"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to open System Settings: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to open System Settings. Please open it manually: System Settings > Privacy & Security > Full Disk Access"
        )

# Playlist creation endpoint (streaming)
@app.post("/create-playlist-optimized-stream")
async def create_playlist_optimized_stream(
    request: Request,
    playlist_name: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    selected_chat_ids: Optional[str] = Form(None),
    existing_playlist_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Create playlist using optimized direct SQL queries with streaming progress."""
    # Support JSON payloads (the macOS app posts JSON) and fall back to form data
    if not all([playlist_name, start_date, end_date, selected_chat_ids]):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            playlist_name = playlist_name or payload.get("playlist_name") or payload.get("playlistName")
            start_date = start_date or payload.get("start_date") or payload.get("startDate")
            end_date = end_date or payload.get("end_date") or payload.get("endDate")
            existing_playlist_id = existing_playlist_id or payload.get("existing_playlist_id") or payload.get("playlist_id")
            if not selected_chat_ids:
                chat_ids_value = payload.get("selected_chat_ids") or payload.get("chat_ids")
                if isinstance(chat_ids_value, list):
                    try:
                        selected_chat_ids = json.dumps(chat_ids_value)
                    except Exception:
                        pass
                elif isinstance(chat_ids_value, str):
                    selected_chat_ids = chat_ids_value
    
    # Provide safe defaults when optional inputs are missing/blank
    now_iso = datetime.now(timezone.utc).isoformat()
    start_date = start_date or "2000-01-01T00:00:00+00:00"
    end_date = end_date or now_iso
    selected_chat_ids = selected_chat_ids or "[]"
    playlist_name = playlist_name or "Dopetracks Playlist"
    
    async def generate_progress():
        try:
            # Validate date strings early to avoid crashing during conversion
            try:
                datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid date format'})}\n\n"
                await asyncio.sleep(0)
                return
            from .processing.imessage_data_processing.optimized_queries import (
                query_messages_with_urls
            )
            from .processing.imessage_data_processing import parsing_utils as pu
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
                    spotify_urls = pu.extract_spotify_urls(str(text))
                    all_urls = pu.extract_all_urls(str(text))
                    
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
                    
                    yield f"data: {json.dumps({'status': 'complete', 'message': f'Successfully added {len(track_ids)} tracks to playlist', 'tracks_added': len(track_ids), 'total_tracks_found': len(track_urls), 'playlist_id': playlist['id'], 'playlist_name': playlist['name'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'playlist': playlist, 'chat_ids': chat_ids, 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                    await asyncio.sleep(0)
                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Failed to add tracks to playlist: {str(e)}', 'tracks_added': 0, 'track_details': track_details})}\n\n"
                    await asyncio.sleep(0)
            else:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No valid tracks to add', 'tracks_added': 0, 'total_tracks_found': len(track_urls), 'playlist_id': playlist['id'], 'playlist_name': playlist['name'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'playlist': playlist, 'chat_ids': chat_ids, 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                await asyncio.sleep(0)
                
        except Exception as e:
            logger.error(f"Error in playlist creation stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)}'})}\n\n"
            await asyncio.sleep(0)
    
    return StreamingResponse(generate_progress(), media_type="text/event-stream")

# Get recent messages for a chat
@app.get("/chat/{chat_id}/recent-messages")
async def get_recent_messages(
    chat_id: int,
    chat_ids: Optional[str] = None,
    canonical_chat_id: Optional[str] = None,
    limit: int = 5,
    offset: int = 0,
    order: str = "desc",
    search: Optional[str] = None,
):
    """Get recent messages for a chat."""
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")
        
        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db:
            raise HTTPException(status_code=500, detail="Failed to prepare messages database")
        
        chat_id_list: List[int] = [chat_id]
        participant_name_map: Dict[str, str] = {}
        if canonical_chat_id:
            # Resolve chat_ids from prepared DB mapping
            try:
                conn_map = sqlite3.connect(prepared_db)
                cur_map = conn_map.cursor()
                cur_map.execute(
                    "SELECT chat_ids FROM chat_groups WHERE canonical_chat_id = ?",
                    (canonical_chat_id,),
                )
                row = cur_map.fetchone()
                if row and row[0]:
                    chat_id_list = [int(x) for x in row[0].split(",") if x.strip()]
                cur_map.close()
                conn_map.close()
            except Exception:
                pass
        elif chat_ids:
            try:
                parsed_ids = [int(x) for x in chat_ids.split(",") if x.strip()]
                if parsed_ids:
                    chat_id_list = parsed_ids
            except Exception:
                pass
        else:
            # If client did not pass group ids, try to find equivalent chats by participants
            equivalents = _find_equivalent_chat_ids(chat_id, source_db)
            if equivalents:
                chat_id_list = equivalents

        # Build participant name map for better sender resolution
        participant_name_map = _build_participant_name_map(source_db, prepared_db, chat_id_list)

        placeholders = ",".join(["?"] * len(chat_id_list))
        conn = sqlite3.connect(prepared_db)
        try:
            cur = conn.cursor()
            order_dir = "DESC" if order.lower() != "asc" else "ASC"
            params: List[Any] = chat_id_list + [limit, offset]
            search_clause = ""
            if search:
                search_clause = "AND m.rowid IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)"
                params = chat_id_list + [search, limit, offset]
            query = f"""
                SELECT
                    m.message_id,
                    m.text,
                    m.date,
                    m.sender_handle,
                    m.is_from_me,
                    m.has_spotify_link,
                    m.spotify_url,
                    m.associated_message_type,
                    m.associated_message_guid,
                    m.message_guid
                FROM messages m
                WHERE m.chat_id IN ({placeholders})
                {search_clause}
                ORDER BY m.date {order_dir}
                LIMIT ?
                OFFSET ?
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            messages_raw = []
            for row in rows:
                (
                    message_id,
                    text,
                    date_val,
                    sender_handle,
                    is_from_me,
                    has_spotify,
                    spotify_url,
                    associated_message_type,
                    associated_message_guid,
                    message_guid,
                ) = row
                messages_raw.append(
                    {
                        "id": str(message_id),
                        "text": text or "",
                        "date": date_val,
                        "sender_handle": sender_handle,
                        "is_from_me": bool(is_from_me),
                        "has_spotify_link": bool(has_spotify),
                        "spotify_url": spotify_url,
                        "associated_message_type": associated_message_type,
                        "associated_message_guid": associated_message_guid,
                        "message_guid": message_guid,
                    }
                )

            # Split base messages and reactions
            base_messages: Dict[str, Dict[str, Any]] = {}
            reactions_by_target: Dict[str, List[Dict[str, Any]]] = {}

            for msg in messages_raw:
                assoc_type = msg.get("associated_message_type")
                is_reaction = assoc_type not in (None, 0)
                sender_handle = msg.get("sender_handle")

                # Resolve sender name
                sender_name = sender_handle or "Unknown"
                if msg.get("is_from_me"):
                    sender_name = "You"
                else:
                    # Try participant map first
                    for v in normalize_handle_variants(sender_handle):
                        if v in participant_name_map:
                            sender_name = participant_name_map[v]
                            break
                    # First try prepared DB contacts
                    if sender_name == sender_handle or sender_name == "Unknown":
                        resolved = _resolve_sender_name_from_prepared(prepared_db, sender_handle)
                        if resolved and resolved.get("full_name"):
                            sender_name = resolved["full_name"]
                        elif sender_name == "Unknown" or sender_name == sender_handle:
                            try:
                                info = get_contact_info_by_handle(sender_handle)
                                if info and info.get("full_name"):
                                    sender_name = info["full_name"]
                            except Exception:
                                pass

                if is_reaction:
                    reaction_type = dictionaries.reaction_dict.get(assoc_type, "reaction")
                    target_guid = msg.get("associated_message_guid")
                    if not target_guid:
                        continue
                    reactions_by_target.setdefault(target_guid, []).append(
                        {
                            "type": reaction_type,
                            "sender": sender_name,
                            "is_from_me": msg.get("is_from_me", False),
                            "date": msg.get("date"),
                            "message_id": msg.get("id"),
                        }
                    )
                else:
                    key = msg.get("message_guid") or msg["id"]
                    base_messages[key] = {
                        "id": msg["id"],
                        "text": msg["text"],
                        "date": msg["date"],
                        "sender": sender_handle,
                        "sender_name": sender_name,
                        "sender_full_name": sender_name,
                        "is_from_me": msg["is_from_me"],
                        "has_spotify_link": msg["has_spotify_link"],
                        "spotify_url": msg["spotify_url"],
                        "reactions": [],
                        "message_guid": msg.get("message_guid"),
                    }

            # Attach reactions to targets
            for target_guid, reacts in reactions_by_target.items():
                target = base_messages.get(target_guid)
                if target:
                    target["reactions"].extend(reacts)

            # Keep ordering of non-reaction messages
            ordered = [
                m for m in messages_raw
                if m.get("associated_message_type") in (None, 0)
            ]
            result_messages = []
            for m in ordered:
                key = m.get("message_guid") or m["id"]
                if key in base_messages:
                    out = base_messages[key].copy()
                    out.pop("message_guid", None)
                    result_messages.append(out)

            return {"messages": result_messages}
        finally:
            conn.close()
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
