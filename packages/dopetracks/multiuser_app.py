"""
Multi-user FastAPI application for Dopetracks.
Ready for local development and production hosting.
"""
import os
import logging
import sys
import tempfile
import sqlite3
import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv

# Add the package to Python path for imports
if __name__ == "__main__":
    package_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(package_path))

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

try:
    from .config import settings
    from .database.connection import get_db, init_database, check_database_health
    from .database.models import User, UserSession, UserUploadedFile, UserDataCache
    from .auth.dependencies import get_current_user, get_current_user_optional
    from .services.user_data import get_user_data_service
    from .api.auth import router as auth_router
    from .api.admin import router as admin_router
except ImportError:
    # Fallback for direct execution
    from config import settings
    from database.connection import get_db, init_database, check_database_health
    from database.models import User, UserSession, UserUploadedFile, UserDataCache
    from auth.dependencies import get_current_user, get_current_user_optional
    from services.user_data import get_user_data_service
    from api.auth import router as auth_router
    from api.admin import router as admin_router

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

# Global processing status tracking
_processing_status = {}

# Load environment variables
# Note: config.py already loads .env, but we load here too for any additional vars
# Make sure we load from project root
from pathlib import Path
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Dopetracks Multi-User Application")
    
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
    
    logger.info("Application startup complete")
    yield
    
    logger.info("Application shutdown")

# Create FastAPI app
app = FastAPI(
    title="Dopetracks Multi-User",
    description="Multi-user playlist generator from iMessage data",
    version="2.0.0",
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

# Include API routers
app.include_router(auth_router)
app.include_router(admin_router)

# Health check endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db_healthy = check_database_health()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "environment": settings.ENVIRONMENT,
        "version": "2.0.0"
    }

# Root route removed - static files (frontend) now handle "/"
# The frontend HTML will be served at http://localhost:8888/
# If you need a root API endpoint, use "/api" or "/health" instead

# Spotify OAuth endpoints (adapted for multi-user)
@app.get("/get-client-id")
async def get_client_id(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get Spotify client ID, redirect URI, and current session ID for OAuth."""
    if not settings.SPOTIFY_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")
    
    if not settings.SPOTIFY_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Spotify redirect URI not configured")
    
    redirect_uri = settings.SPOTIFY_REDIRECT_URI
    
    # Validate redirect URI
    if "localhost" in redirect_uri:
        logger.error(f"INVALID redirect URI contains 'localhost': {redirect_uri}")
        logger.error("Spotify requires 127.0.0.1, not localhost!")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Redirect URI contains 'localhost'. Spotify requires '127.0.0.1'. Please update SPOTIFY_REDIRECT_URI in .env file and restart server."
        )
    
    # Get session ID and user using the auth dependency (more reliable)
    from .auth.dependencies import get_current_user_optional, get_session_id_from_cookie
    current_user = None
    session_id = None
    
    # Try to get session ID from cookie
    try:
        session_id = get_session_id_from_cookie(request.cookies.get("dopetracks_session"))
    except Exception as e:
        logger.debug(f"Could not get session ID from cookie dependency: {e}")
        # Fallback to direct cookie access
        session_id = request.cookies.get("dopetracks_session")
    
    # Try to get user using the dependency
    try:
        current_user = get_current_user_optional(db=db, session_id=session_id)
        if current_user:
            logger.info(f"OAuth request - User authenticated: {current_user.username} (ID: {current_user.id})")
            # If we have a user but no session_id, try to get it from the cookie again
            if not session_id:
                session_id = request.cookies.get("dopetracks_session")
    except Exception as e:
        logger.warning(f"Could not get user from session: {e}")
    
    # Log all cookies for debugging
    all_cookies = list(request.cookies.keys())
    logger.info(f"OAuth request - All cookies: {all_cookies}")
    logger.info(f"OAuth request - Client ID: {settings.SPOTIFY_CLIENT_ID[:10]}..., Redirect URI: {redirect_uri}, Session ID present: {bool(session_id)}, User authenticated: {current_user is not None}")
    
    if not session_id and current_user:
        logger.warning("Session ID not in cookie but user is authenticated - this is unusual")
    
    return {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "redirect_uri": redirect_uri,  # CRITICAL: Must match Spotify Dashboard exactly
        "session_id": session_id,  # Pass session ID so frontend can include it in state parameter
        "authenticated": current_user is not None  # Also return auth status
    }

@app.get("/callback")
async def spotify_callback(
    request: Request,
    code: str = None,
    error: str = None,
    state: str = None,  # OAuth state parameter (contains session ID)
    db: Session = Depends(get_db)
):
    """Handle Spotify OAuth callback."""
    # Log all query parameters for debugging
    query_params = dict(request.query_params)
    logger.info(f"Callback received - Query params: {query_params}")
    logger.info(f"Code: {code is not None}, Error: {error}, State: {state}")
    
    # Try to get current user from multiple sources
    # 1. First try cookie (works if browser sends it)
    # 2. Then try state parameter (more reliable for cross-site redirects)
    from .auth.dependencies import get_current_user_optional
    current_user = None
    session_id = None
    
    # Try cookie first
    try:
        session_id = request.cookies.get("dopetracks_session")
        logger.info(f"Cookie check - Session ID from cookie: {session_id[:20] + '...' if session_id else 'None'}")
        if session_id:
            from .auth.security import get_current_user_from_session
            current_user = get_current_user_from_session(db, session_id)
            logger.info(f"Found user from cookie: {current_user.username if current_user else 'None'}")
    except Exception as e:
        logger.warning(f"Could not get user from cookie: {e}")
    
    # If no user from cookie, try state parameter
    if not current_user and state:
        logger.info(f"Trying state parameter - State value: {state[:20] + '...' if len(state) > 20 else state}")
        try:
            # State parameter contains the session ID we passed
            session_id = state
            from .auth.security import get_current_user_from_session
            current_user = get_current_user_from_session(db, session_id)
            logger.info(f"Found user from state parameter: {current_user.username if current_user else 'None'}")
        except Exception as e:
            logger.warning(f"Could not get user from state parameter: {e}")
    
    # Log all cookies for debugging
    logger.info(f"All cookies received: {list(request.cookies.keys())}")
    logger.info(f"Session cookie value: {request.cookies.get('dopetracks_session', 'NOT SET')}")
    logger.info(f"State parameter received: {state}")
    
    # Check for OAuth errors from Spotify
    if error:
        logger.error(f"Spotify OAuth error: {error}")
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Spotify Authorization Failed</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #dc3545;
                    color: white;
                    text-align: center;
                }}
                .container {{
                    background: rgba(255, 255, 255, 0.1);
                    padding: 2rem;
                    border-radius: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Spotify Authorization Failed</h1>
                <p>Error: {error}</p>
                <p><a href="/" style="color: white; text-decoration: underline;">Return to app</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    if not code:
        logger.error("Spotify callback called without authorization code")
        error_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Code Missing</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #ffc107;
                    color: #333;
                    text-align: center;
                }
                .container {
                    background: rgba(255, 255, 255, 0.9);
                    padding: 2rem;
                    border-radius: 10px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ Authorization Code Missing</h1>
                <p>Please try authorizing again.</p>
                <p><a href="/">Return to app</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)
    
    # Check if user is authenticated
    if not current_user:
        logger.warning("Spotify callback received but user not authenticated")
        logger.warning(f"Session cookie present: {bool(request.cookies.get('dopetracks_session'))}")
        logger.warning(f"All cookies: {list(request.cookies.keys())}")
        logger.warning(f"State parameter: {state}")
        
        # Redirect to login page with a message, preserving the code temporarily
        # We'll store the code in a temporary session or pass it via URL
        # For now, show a helpful error page that redirects to login
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Required</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: #007bff;
                    color: white;
                    text-align: center;
                }}
                .container {{
                    background: rgba(255, 255, 255, 0.1);
                    padding: 2rem;
                    border-radius: 10px;
                    max-width: 500px;
                }}
                .debug {{
                    font-size: 0.8em;
                    margin-top: 20px;
                    padding: 10px;
                    background: rgba(0,0,0,0.2);
                    border-radius: 5px;
                    text-align: left;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ Authentication Required</h1>
                <p>You need to be logged in to complete Spotify authorization.</p>
                <p><strong>Please:</strong></p>
                <ol style="text-align: left; display: inline-block;">
                    <li>Go back to the app at <a href="/" style="color: #ffeb3b;">http://127.0.0.1:8888/</a></li>
                    <li>Make sure you're logged in (see your username in top bar)</li>
                    <li>Then click "Authorize Spotify" again</li>
                </ol>
                <div class="debug">
                    <strong>Debug Info:</strong><br>
                    Code received: {'Yes' if code else 'No'}<br>
                    Session cookie: {'Present' if request.cookies.get('dopetracks_session') else 'Missing'}<br>
                    State parameter: {'Present' if state else 'Missing'}
                </div>
                <p style="margin-top: 20px;">
                    <strong>What to do:</strong><br>
                    1. Make sure you're logged in at <a href="/" style="color: #ffeb3b;">http://127.0.0.1:8888/</a><br>
                    2. Check that you see your username in the top bar<br>
                    3. Then click "Authorize Spotify" again
                </p>
                <p style="margin-top: 20px;"><a href="/" style="color: white; text-decoration: underline; font-weight: bold;">← Return to app and log in</a></p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=401)
    
    import requests
    
    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "client_secret": settings.SPOTIFY_CLIENT_SECRET,
    }
    
    logger.info(f"Exchanging Spotify authorization code for tokens")
    logger.info(f"Using redirect URI: {settings.SPOTIFY_REDIRECT_URI}")
    logger.info(f"Client ID: {settings.SPOTIFY_CLIENT_ID[:10]}...")
    
    response = requests.post(token_url, data=payload)
    
    if response.status_code != 200:
        error_detail = response.text
        error_json = None
        try:
            error_json = response.json()
            error_detail = error_json.get('error_description', error_json.get('error', error_detail))
        except:
            pass
        
        logger.error(f"Spotify token exchange failed (status {response.status_code}): {error_detail}")
        logger.error(f"Redirect URI used: {settings.SPOTIFY_REDIRECT_URI}")
        logger.error(f"Request payload (without secrets): grant_type=authorization_code, redirect_uri={settings.SPOTIFY_REDIRECT_URI}")
        
        # Provide more helpful error messages
        if "invalid_client" in error_detail.lower() or "invalid redirect" in error_detail.lower():
            error_msg = f"Redirect URI mismatch. Make sure '{settings.SPOTIFY_REDIRECT_URI}' is exactly in your Spotify Dashboard Redirect URIs."
        elif "invalid_grant" in error_detail.lower():
            error_msg = "Authorization code expired or already used. Please try authorizing again."
        else:
            error_msg = f"Spotify authorization failed: {error_detail}"
        
        raise HTTPException(
            status_code=400, 
            detail=error_msg
        )
    
    tokens = response.json()
    
    # Store tokens for the user
    user_data_service = get_user_data_service(db, current_user)
    success = user_data_service.store_spotify_tokens(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in"),
        scope=tokens.get("scope")
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store Spotify tokens")
    
    logger.info(f"Spotify tokens stored for user {current_user.username}")
    
    # Return HTML that automatically redirects to the main app
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spotify Authorization Successful</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #1db954, #191414);
                color: white;
                text-align: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                padding: 2rem;
                border-radius: 10px;
                backdrop-filter: blur(10px);
            }
            .success-icon {
                font-size: 3rem;
                margin-bottom: 1rem;
            }
            .loading {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid rgba(255,255,255,.3);
                border-radius: 50%;
                border-top-color: #1db954;
                animation: spin 1s ease-in-out infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        </style>
        <script>
            // Redirect to main app and trigger status check
            // Use replace to avoid back button issues
            setTimeout(function() {
                window.location.replace('/');
            }, 1500);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="success-icon">✅</div>
            <h1>Spotify Authorization Successful!</h1>
            <p>You can now access your Spotify playlists.</p>
            <p>Redirecting to the main app... <span class="loading"></span></p>
            <p><a href="/index.html" style="color: #1db954; text-decoration: none;">Click here if you're not redirected automatically</a></p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/user-profile")
async def get_user_spotify_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's Spotify profile."""
    user_data_service = get_user_data_service(db, current_user)
    spotify_tokens = user_data_service.get_spotify_tokens()
    
    if not spotify_tokens:
        # This is expected if user hasn't authorized Spotify yet - log at debug level
        logger.debug(f"User {current_user.username} has not authorized Spotify yet")
        raise HTTPException(status_code=401, detail="Spotify not authorized")
    
    import requests
    headers = {"Authorization": f"Bearer {spotify_tokens.access_token}"}
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    
    if response.status_code != 200:
        logger.warning(f"Invalid Spotify token for user {current_user.username}: {response.status_code}")
        raise HTTPException(status_code=401, detail="Invalid Spotify token")
    
    return response.json()

@app.get("/user-playlists")
async def get_user_playlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's Spotify playlists."""
    user_data_service = get_user_data_service(db, current_user)
    spotify_tokens = user_data_service.get_spotify_tokens()
    
    if not spotify_tokens:
        raise HTTPException(status_code=401, detail="Spotify not authorized")
    
    import requests
    headers = {"Authorization": f"Bearer {spotify_tokens.access_token}"}
    response = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)
    
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Failed to fetch playlists")
    
    playlists = response.json().get("items", [])
    return [{"name": p["name"], "id": p["id"]} for p in playlists]

# System Setup endpoints
@app.get("/validate-username")
async def validate_username(
    username: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate if the given macOS username has access to Messages database."""
    import sqlite3
    from pathlib import Path
    
    try:
        # Common paths where Messages database might be located
        possible_paths = [
            f"/Users/{username}/Library/Messages/chat.db",
            f"/Users/{username}/Library/Messages/chat.db-shm",
            f"/Users/{username}/Library/Messages/chat.db-wal"
        ]
        
        # Check if the main chat.db file exists and is accessible
        chat_db_path = f"/Users/{username}/Library/Messages/chat.db"
        
        if not os.path.exists(chat_db_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Messages database not found at {chat_db_path}. Make sure you have the correct username and have granted access to the Messages app."
            )
        
        # Try to open and query the database to ensure it's valid
        try:
            conn = sqlite3.connect(chat_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='message';")
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                raise HTTPException(
                    status_code=400,
                    detail="Found database file but it doesn't appear to be a valid Messages database."
                )
                
        except sqlite3.Error as e:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot access Messages database. You may need to grant Full Disk Access to your terminal/IDE in System Preferences > Security & Privacy > Privacy > Full Disk Access. Error: {str(e)}"
            )
        
        # Store the validated path as preferred_db_path
        user_data_service = get_user_data_service(db, current_user)
        user_data_service.set_preferred_db_path(chat_db_path)
        return {
            "message": "Messages database found and accessible",
            "filepath": chat_db_path,
            "username": username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating username {username}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error validating system access: {str(e)}"
        )

@app.post("/validate-chat-file")
@app.post("/validate-chat-file/")  # Handle both with and without trailing slash
async def validate_chat_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate uploaded Messages database file."""
    try:
        # Check file extension
        if not file.filename.endswith('.db'):
            raise HTTPException(
                status_code=400,
                detail="File must be a .db file (SQLite database)"
            )
        
        # Read file content
        content = await file.read()
        
        # Create temporary file to validate
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Validate it's a proper Messages database
            conn = sqlite3.connect(temp_file_path)
            cursor = conn.cursor()
            
            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('message', 'handle', 'chat');")
            tables = cursor.fetchall()
            
            if len(tables) < 3:
                raise HTTPException(
                    status_code=400,
                    detail="This doesn't appear to be a valid Messages database. Missing required tables."
                )
            
            # Get some basic stats
            cursor.execute("SELECT COUNT(*) FROM message;")
            message_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM handle;")
            handle_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Store the file for the user (you might want to implement proper file storage)
            user_data_service = get_user_data_service(db, current_user)
            
            # Save uploaded file for the user and set as preferred_db_path
            saved_file = user_data_service.save_uploaded_file(content, file.filename, file.content_type)
            if saved_file:
                user_data_service.set_preferred_db_path(saved_file.storage_path)
            
            return {
                "message": f"Valid Messages database uploaded successfully. Found {message_count} messages and {handle_count} contacts.",
                "filepath": file.filename,
                "message_count": message_count,
                "handle_count": handle_count
            }
            
        except sqlite3.Error as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid database file: {str(e)}"
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating uploaded file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing uploaded file: {str(e)}"
        )

# File upload endpoint
@app.post("/upload-chat-file")
async def upload_chat_file(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload chat database file for processing."""
    from fastapi import File, UploadFile, Form
    
    # This would be properly implemented with File parameter
    # For now, placeholder that shows the structure
    
    return {
        "message": "File upload endpoint - implementation needed",
        "user_id": current_user.id
    }

# Data processing endpoints
@app.get("/chat-search-status")
async def chat_search_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get chat search processing status for the current user."""
    user_data_service = get_user_data_service(db, current_user)
    
    # Check if user has cached data
    has_messages = user_data_service.get_cached_data("messages") is not None
    has_contacts = user_data_service.get_cached_data("contacts") is not None
    
    # Check if user is currently processing
    user_processing = _processing_status.get(current_user.id, {}).get("is_processing", False)
    
    return {
        "has_cached_data": has_messages and has_contacts,
        "messages_cached": has_messages,
        "contacts_cached": has_contacts,
        "is_processing": user_processing
    }

@app.get("/chat-search-progress")
async def chat_search_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [DEPRECATED] Server-Sent Events endpoint for real-time progress updates during data preparation.
    
    This endpoint is deprecated. Use the new optimized endpoints instead:
    - GET /chats - Get list of all chats (no processing needed)
    - GET /chat-search-optimized - Search chats (no processing needed)
    - POST /create-playlist-optimized - Create playlists (no processing needed)
    
    The new endpoints query the database directly and don't require upfront processing.
    """
    user_data_service = get_user_data_service(db, current_user)
    
    # Initialize user processing status if not exists
    if current_user.id not in _processing_status:
        _processing_status[current_user.id] = {"is_processing": False}
    
    # Check if data already exists
    has_messages = user_data_service.get_cached_data("messages") is not None
    has_contacts = user_data_service.get_cached_data("contacts") is not None
    
    async def generate_progress():
        try:
            if has_messages and has_contacts:
                yield f"data: {json.dumps({'status': 'completed', 'message': 'Data already prepared and cached!'})}\n\n"
                return
            
            # Check if already processing
            if _processing_status[current_user.id]["is_processing"]:
                yield f"data: {json.dumps({'status': 'already_processing', 'message': 'Data processing already in progress'})}\n\n"
                return
            
            # Start processing
            _processing_status[current_user.id]["is_processing"] = True
            
            yield f"data: {json.dumps({'status': 'starting', 'message': 'Starting data preparation...'})}\n\n"
            await asyncio.sleep(0.5)
            
            # Use preferred_db_path if set
            preferred_db_path = user_data_service.get_preferred_db_path()
            if preferred_db_path and os.path.exists(preferred_db_path):
                messages_db_path = preferred_db_path
                yield f"data: {json.dumps({'status': 'progress', 'message': f'Using preferred Messages database: {preferred_db_path}'})}\n\n"
            else:
                # First check if user uploaded a custom database file
                uploaded_files = user_data_service.get_uploaded_files()
                for file in uploaded_files:
                    if file.original_filename.endswith('.db'):
                        # Use uploaded file
                        messages_db_path = file.storage_path
                        yield f"data: {json.dumps({'status': 'progress', 'message': f'Using uploaded database: {file.original_filename}'})}\n\n"
                        break
            
            # If no uploaded file, try to find the correct Messages database path
            if not messages_db_path:
                # Try multiple approaches to find the Messages database
                # import os  # Removed duplicate import
                # First, try the system username (which is often different from app username)
                system_user = os.path.expanduser("~").split("/")[-1]  # Get actual system username
                system_path = f"/Users/{system_user}/Library/Messages/chat.db"
                # Also try the application username path
                app_username_path = f"/Users/{current_user.username}/Library/Messages/chat.db"
                # Try common default path
                default_path = os.path.expanduser("~/Library/Messages/chat.db")
                # Check which paths exist and are accessible
                for path_description, path in [
                    ("system user path", system_path),
                    ("application username path", app_username_path), 
                    ("home directory path", default_path)
                ]:
                    if os.path.exists(path):
                        try:
                            # Test database access
                            import sqlite3
                            conn = sqlite3.connect(path)
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM message LIMIT 1;")
                            conn.close()
                            messages_db_path = path
                            yield f"data: {json.dumps({'status': 'progress', 'message': f'Found Messages database at {path_description}: {path}'})}\n\n"
                            break
                        except Exception as e:
                            yield f"data: {json.dumps({'status': 'progress', 'message': f'Found database at {path} but cannot access it: {str(e)}'})}\n\n"
                            continue
                if not messages_db_path:
                    raise Exception(f"No accessible Messages database found. Tried paths: {system_path}, {app_username_path}, {default_path}")
            
            await asyncio.sleep(0.5)
            
            # Import the actual data processing modules
            try:
                from .processing.prepare_data_main import pull_and_clean_messages
                from .processing.spotify_interaction import spotify_db_manager as sdm
                
                yield f"data: {json.dumps({'status': 'progress', 'message': 'Starting data extraction (this may take 40-60 seconds)...'})}\n\n"
                await asyncio.sleep(1)
                
                # Run actual data processing in thread to avoid blocking
                loop = asyncio.get_event_loop()
                processed_data = await loop.run_in_executor(None, pull_and_clean_messages, messages_db_path)
                
                yield f"data: {json.dumps({'status': 'progress', 'message': 'Data extraction completed! Processing Spotify URLs...'})}\n\n"
                await asyncio.sleep(0.5)
                
                # Process Spotify URLs
                await loop.run_in_executor(None, sdm.main, processed_data['messages'], 'all_spotify_links')
                
                yield f"data: {json.dumps({'status': 'progress', 'message': 'Caching processed data...'})}\n\n"
                await asyncio.sleep(0.5)
                
                # Cache the real processed data using proper DataFrame serialization
                import pickle
                import base64
                
                def serialize_dataframe(df):
                    """Serialize DataFrame to base64 encoded pickle string"""
                    return base64.b64encode(pickle.dumps(df)).decode('utf-8')
                
                # Store serialized DataFrames
                for key, data in processed_data.items():
                    if hasattr(data, 'to_dict'):  # It's a DataFrame
                        serialized_data = {"_type": "dataframe", "_data": serialize_dataframe(data)}
                    else:
                        serialized_data = data
                    user_data_service.cache_data(key, serialized_data)
                
                yield f"data: {json.dumps({'status': 'completed', 'message': 'Data preparation completed successfully! You can now search chats.'})}\n\n"
                
            except Exception as e:
                logger.error(f"Data processing error: {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'Error during data processing: {str(e)}'})}\n\n"
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)}'})}\n\n"
        finally:
            # Reset processing status
            _processing_status[current_user.id]["is_processing"] = False
    
    return StreamingResponse(generate_progress(), media_type="text/event-stream")

def deserialize_dataframe(data):
    """Deserialize base64 encoded pickle string back to DataFrame"""
    import pickle
    import base64
    return pickle.loads(base64.b64decode(data.encode('utf-8')))

@app.get("/chat-search")
async def chat_search(
    query: str,
    use_optimized: bool = True,  # New parameter to switch between old and new approach
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for chats by name.
    
    If use_optimized=True (default): Uses direct SQL queries (no upfront processing needed)
    If use_optimized=False: Uses cached data (requires data preparation first)
    """
    try:
        # Try optimized approach first (default)
        if use_optimized:
            try:
                from .processing.imessage_data_processing.optimized_queries import (
                    get_user_db_path, search_chats_by_name
                )
                
                user_data_service = get_user_data_service(db, current_user)
                db_path = get_user_db_path(user_data_service)
                
                if db_path and os.path.exists(db_path):
                    results = search_chats_by_name(db_path, query)
                    return results
                else:
                    # Fall back to old approach if no db path
                    logger.warning("No database path found, falling back to cached data approach")
                    use_optimized = False
            except Exception as e:
                logger.warning(f"Optimized search failed, falling back to cached data: {e}")
                use_optimized = False
        
        # Fall back to old cached data approach
        if not use_optimized:
            user_data_service = get_user_data_service(db, current_user)
            messages_data = user_data_service.get_cached_data("messages")
            if messages_data is None:
                raise HTTPException(
                    status_code=400, 
                    detail="No chat data available. Please complete data preparation first or use optimized search (use_optimized=true)."
                )
        import pandas as pd
        # Deserialize DataFrame if needed
        if isinstance(messages_data, dict) and messages_data.get("_type") == "dataframe":
            messages_df = deserialize_dataframe(messages_data["_data"])
        else:
            return []
        
        # Simple search on chat_name
        mask = messages_df['chat_name'].str.contains(query, case=False, na=False)
        filtered = messages_df[mask]
        if filtered.empty:
            return []
        
        # Debug logging
        logger.info(f"Chat search - Available columns: {list(messages_df.columns)}")
        logger.info(f"Chat search - Current username: {current_user.username}")
        logger.info(f"Chat search - Total messages in DataFrame: {len(messages_df)}")
        
        # Check for empty data issues
        if 'spotify_song_links' in messages_df.columns:
            non_empty_spotify = messages_df['spotify_song_links'].dropna()
            logger.info(f"Chat search - Messages with Spotify links: {len(non_empty_spotify)}")
            if len(non_empty_spotify) > 0:
                logger.info(f"Chat search - Sample Spotify links: {non_empty_spotify.head().tolist()}")
        
        if not filtered.empty:
            logger.info(f"Chat search - Sample sender values: {filtered['sender'].head().tolist() if 'sender' in filtered.columns else 'No sender column'}")
            logger.info(f"Chat search - Sample sender_handle_id values: {filtered['sender_handle_id'].head().tolist() if 'sender_handle_id' in filtered.columns else 'No sender_handle_id column'}")
            # Show actual values from a specific chat
            sample_chat = filtered['chat_name'].iloc[0]
            sample_group = filtered[filtered['chat_name'] == sample_chat]
            logger.info(f"Chat search - Sample chat '{sample_chat}' has {len(sample_group)} messages")
            if 'sender' in sample_group.columns:
                logger.info(f"Chat search - Unique senders in sample chat: {sample_group['sender'].unique().tolist()}")
        
        # Check for Spotify-related columns
        spotify_cols = [col for col in messages_df.columns if any(term in col.lower() for term in ['spotify', 'song', 'link', 'url', 'music'])]
        logger.info(f"Chat search - Potential Spotify columns: {spotify_cols}")
        
        results = []
        for chat_name, group in filtered.groupby('chat_name'):
            try:
                # Safely get members count
                members = None
                if 'sender_handle_id' in group.columns:
                    members = int(group['sender_handle_id'].nunique())
                elif 'sender' in group.columns:
                    members = int(group['sender'].nunique())
                
                # Safely get user messages count - use username instead of ID
                user_messages = None
                if 'is_from_me' in group.columns:
                    # Use is_from_me column to count messages sent by the user
                    user_messages = int(group['is_from_me'].sum())
                elif 'sender' in group.columns:
                    # Fallback to username matching if is_from_me doesn't exist
                    sender_mask = group['sender'].astype(str) == str(current_user.username)
                    user_messages = int(sender_mask.sum())
                elif 'sender_handle_id' in group.columns:
                    # Skip user message counting for now since we have numeric IDs, not usernames
                    # TODO: Map handle_id to username using handles/contacts data
                    user_messages = None
                
                # Count unique Spotify URLs safely
                spotify_urls = 0
                most_recent_song_date = None
                if 'spotify_song_links' in group.columns:
                    # Count non-empty lists
                    non_empty_links = group['spotify_song_links'].apply(lambda x: len(x) if isinstance(x, list) else 0)
                    total_links = non_empty_links.sum()
                    
                    if total_links > 0:
                        # Get unique URLs
                        all_urls = []
                        for links in group['spotify_song_links']:
                            if isinstance(links, list):
                                all_urls.extend(links)
                        spotify_urls = len(set(all_urls))
                        logger.debug(f"Chat '{chat_name}' - Found {spotify_urls} unique Spotify URLs from {total_links} total links")
                        
                        # Get most recent song date
                        if 'date' in group.columns:
                            # Find rows with non-empty spotify links
                            mask = non_empty_links > 0
                            dates_with_songs = group.loc[mask, 'date']
                            if not dates_with_songs.empty:
                                most_recent_song_date = dates_with_songs.max()
                    else:
                        logger.debug(f"Chat '{chat_name}' - No Spotify links found")
                else:
                    logger.debug(f"Chat '{chat_name}' - spotify_song_links column not found")
                
                results.append({
                    "name": chat_name,
                    "members": int(members) if members is not None else 0,
                    "total_messages": int(group.shape[0]),
                    "user_messages": int(user_messages) if user_messages is not None else 0,
                    "spotify_urls": int(spotify_urls),  # Always an int, never None
                    "most_recent_song_date": most_recent_song_date
                })
            except Exception as inner_e:
                logger.error(f"Error processing chat '{chat_name}': {inner_e}", exc_info=True)
                # Continue with other chats even if one fails
                continue
        
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )

# ============================================================================
# OPTIMIZED ENDPOINTS (Full Refactor - No Upfront Processing Required)
# ============================================================================

@app.get("/chats")
async def get_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all chats with basic statistics.
    Fast query - no message processing needed.
    Replaces the need for upfront data preparation.
    """
    try:
        from .processing.imessage_data_processing.optimized_queries import (
            get_user_db_path, get_chat_list
        )
        
        user_data_service = get_user_data_service(db, current_user)
        db_path = get_user_db_path(user_data_service)
        
        if not db_path:
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please validate username or upload database file first."
            )
        
        if not os.path.exists(db_path):
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )
        
        chats = get_chat_list(db_path)
        return chats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving chats: {str(e)}"
        )

@app.get("/chat-search-optimized")
async def chat_search_optimized(
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Optimized chat search using direct SQL queries.
    No upfront processing required.
    """
    try:
        from .processing.imessage_data_processing.optimized_queries import (
            get_user_db_path, search_chats_by_name
        )
        
        user_data_service = get_user_data_service(db, current_user)
        db_path = get_user_db_path(user_data_service)
        
        if not db_path:
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please validate username or upload database file first."
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
        logger.error(f"Error in optimized chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )

@app.post("/create-playlist-optimized")
async def create_playlist_optimized(
    playlist_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    selected_chat_ids: str = Form(...),  # JSON string of chat IDs (integers)
    existing_playlist_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create playlist using optimized direct SQL queries.
    Only processes messages with Spotify links from selected chats (by chat_id) and date range.
    No upfront processing required.
    
    Use chat_id instead of chat_name to avoid ambiguity with duplicate chat names.
    """
    try:
        from .processing.imessage_data_processing.optimized_queries import (
            get_user_db_path, query_spotify_messages, query_messages_with_urls, extract_spotify_urls, extract_all_urls
        )
        from .processing.spotify_interaction import spotify_db_manager as sdm
        from .processing.spotify_interaction import create_spotify_playlist as csp
        
        # Parse selected chat IDs
        try:
            chat_ids = json.loads(selected_chat_ids) if selected_chat_ids else []
            # Ensure they're integers
            chat_ids = [int(cid) for cid in chat_ids]
        except (json.JSONDecodeError, ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid chat selection format. Expected JSON array of chat IDs (integers)."
            )
        
        if not chat_ids:
            raise HTTPException(
                status_code=400,
                detail="Please select at least one chat."
            )
        
        # Get user's database path
        user_data_service = get_user_data_service(db, current_user)
        db_path = get_user_db_path(user_data_service)
        
        if not db_path:
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please validate username or upload database file first."
            )
        
        # Query messages with ANY URLs (not just Spotify) to capture Apple Music, YouTube, etc.
        logger.info(f"Querying messages with URLs from {len(chat_ids)} chats (by ID), {start_date} to {end_date}")
        messages_df = query_messages_with_urls(db_path, chat_ids, start_date, end_date)
        
        if messages_df.empty:
            return {
                "status": "warning",
                "message": "No messages with URLs found for the selected criteria.",
                "tracks_added": 0
            }
        
        # Extract Spotify URLs from messages and track which message each URL came from
        # Use final_text if available (from query_spotify_messages), otherwise fall back to text
        text_column = 'final_text' if 'final_text' in messages_df.columns else 'text'
        
        # Map URLs to their source messages
        url_to_message = {}  # url -> {message_text, sender_name, is_from_me, date, chat_name, entity_type}
        skipped_urls = []  # List of non-track Spotify links with their info
        other_links = []  # List of all non-Spotify links (Instagram, YouTube, Apple Music, etc.)
        
        for idx, row in messages_df.iterrows():
            text = row.get(text_column)
            if pd.notna(text) and text:
                # Extract Spotify URLs for processing
                spotify_urls = extract_spotify_urls(str(text))
                # Extract all URLs for tracking other links
                all_urls = extract_all_urls(str(text))
                
                # Debug logging
                if len(all_urls) > 0:
                    logger.debug(f"Found {len(all_urls)} URLs in message: {[u.get('type') for u in all_urls]}")
                
                # Determine sender name
                if bool(row.get('is_from_me', False)):
                    sender_name = "You"
                else:
                    # Use sender_contact (phone/email) if available, otherwise chat_name
                    sender_contact = row.get('sender_contact')
                    if pd.notna(sender_contact) and sender_contact:
                        sender_name = str(sender_contact)
                    else:
                        sender_name = row.get('chat_name', 'Unknown Sender')
                
                message_info = {
                    "message_text": str(text),  # Store full message text (no truncation)
                    "sender_name": sender_name,
                    "is_from_me": bool(row.get('is_from_me', False)),
                    "date": row.get('date_utc', ''),
                    "chat_name": row.get('chat_name', '')
                }
                
                # Process Spotify URLs
                for url in spotify_urls:
                    # Extract entity type from URL
                    _, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                    
                    if '/track/' in url or entity_type == 'track':
                        # Track URLs - add to processing list
                        if url not in url_to_message:
                            url_to_message[url] = {**message_info, "entity_type": entity_type or "track"}
                    else:
                        # Non-track Spotify links (albums, playlists, artists, etc.) - track for reporting
                        skipped_info = {
                            "url": url,
                            "entity_type": entity_type or "unknown",
                            "spotify_id": spotify_id,
                            **message_info
                        }
                        skipped_urls.append(skipped_info)
                
                # Track all non-Spotify links
                spotify_url_set = set(spotify_urls)
                for url_info in all_urls:
                    url = url_info["url"]
                    url_type = url_info["type"]
                    # Only track non-Spotify links (exclude Spotify links)
                    if url_type != "spotify" and url not in spotify_url_set:
                        other_link_info = {
                            "url": url,
                            "link_type": url_type,
                            **message_info
                        }
                        other_links.append(other_link_info)
                        logger.debug(f"Added {url_type} link: {url[:50]}...")
        
        track_urls = list(url_to_message.keys())
        
        if not track_urls:
            return {
                "status": "warning",
                "message": "No Spotify track links found in the selected messages.",
                "tracks_added": 0,
                "track_details": []
            }
        
        logger.info(f"Found {len(track_urls)} unique Spotify track URLs")
        
        # Get Spotify tokens
        spotify_tokens = user_data_service.get_spotify_tokens()
        if not spotify_tokens:
            raise HTTPException(
                status_code=401,
                detail="Spotify not authorized. Please authorize Spotify first."
            )
        
        # Create Spotify client
        import spotipy
        sp = spotipy.Spotify(auth=spotify_tokens.access_token)
        
        # Get user ID and create or find playlist
        user_id = csp.get_user_id(sp)
        
        # If existing_playlist_id is provided, use that playlist
        if existing_playlist_id:
            try:
                playlist = sp.playlist(existing_playlist_id)
                logger.info(f"Using existing playlist: {playlist['name']} (ID: {existing_playlist_id})")
            except Exception as e:
                logger.warning(f"Could not access playlist {existing_playlist_id}: {e}")
                # Fall back to find_or_create by name
                playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
        else:
            # Find or create playlist by name
            playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
        
        # Get existing tracks
        existing_tracks = csp.get_all_playlist_items(sp, playlist['id'])
        existing_track_ids = set(csp.get_song_ids_from_spotify_items(existing_tracks))
        
        # Process URLs to get track IDs and track details
        track_details = []  # List of dicts with url, track_id, status, error, track_name, artist
        track_ids = []
        
        for url in track_urls:
            # Get message info for this URL
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
                    continue
                
                if not spotify_id:
                    track_info["status"] = "error"
                    track_info["error"] = "Could not extract Spotify ID from URL"
                    track_details.append(track_info)
                    continue
                
                track_info["track_id"] = spotify_id
                
                # Validate format
                if not (spotify_id.isalnum() and 15 <= len(spotify_id) <= 22):
                    track_info["status"] = "error"
                    track_info["error"] = f"Invalid ID format (length: {len(spotify_id)}, must be 15-22 alphanumeric chars)"
                    track_details.append(track_info)
                    continue
                
                # Check if already in playlist
                if spotify_id in existing_track_ids:
                    track_info["status"] = "skipped"
                    track_info["error"] = "Already in playlist"
                    # Try to get track info for display
                    try:
                        track_data = sp.track(spotify_id)
                        track_info["track_name"] = track_data.get("name", "Unknown")
                        track_info["artist"] = ", ".join([a["name"] for a in track_data.get("artists", [])])
                        track_info["spotify_url"] = track_data.get("external_urls", {}).get("spotify")
                    except:
                        pass
                    track_details.append(track_info)
                    continue
                
                # Validate with Spotify API and get track info
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
                    if "Invalid base62 id" in error_str or "invalid id" in error_str.lower() or "code:-1" in error_str:
                        track_info["error"] = f"Invalid track ID: {error_str[:200]}"
                    else:
                        track_info["error"] = f"Spotify API error: {error_str[:200]}"
                    track_details.append(track_info)
                    
            except Exception as e:
                track_info["status"] = "error"
                track_info["error"] = f"Processing error: {str(e)[:200]}"
                track_details.append(track_info)
        
        # Update track_details status for tracks that will be added
        valid_track_ids = [t["track_id"] for t in track_details if t["status"] == "valid"]
        
        # Add tracks to playlist with error handling
        if valid_track_ids:
            try:
                added_count = csp.add_tracks_to_playlist(sp, playlist['id'], valid_track_ids)
                logger.info(f"Added {added_count} tracks to playlist '{playlist_name}'")
                
                # Update status for successfully added tracks
                added_track_ids = set(valid_track_ids[:added_count] if added_count <= len(valid_track_ids) else valid_track_ids)
                for track_info in track_details:
                    if track_info["track_id"] in added_track_ids:
                        track_info["status"] = "added"
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error adding tracks to playlist: {error_msg}")
                
                # Try to identify which track ID(s) are problematic
                problematic_ids = []
                if "Invalid base62 id" in error_msg or "invalid id" in error_msg.lower() or "code:-1" in error_msg:
                    logger.info(f"Invalid track ID error detected. Testing {len(valid_track_ids)} track IDs to identify problematic ones...")
                    
                    # First, validate each ID format before testing with API
                    for track_id in valid_track_ids:
                        # Check format: should be base62 alphanumeric, 15-22 chars
                        if not (track_id and track_id.isalnum() and 15 <= len(track_id) <= 22):
                            problematic_ids.append(track_id)
                            logger.warning(f"Invalid track ID format detected: {track_id} (length: {len(track_id) if track_id else 0})")
                    
                    # If format validation didn't catch all, test remaining IDs with Spotify API
                    remaining_ids = [tid for tid in valid_track_ids if tid not in problematic_ids]
                    if remaining_ids:
                        logger.info(f"Testing {len(remaining_ids)} track IDs with Spotify API...")
                        for track_id in remaining_ids:
                            try:
                                # Try to get track info - if this fails, the ID is invalid
                                sp.track(track_id)
                            except Exception as track_error:
                                problematic_ids.append(track_id)
                                error_str = str(track_error)
                                logger.warning(f"Invalid track ID detected via API: {track_id} - {error_str[:100]}")
                    
                    if problematic_ids:
                        # Update track_details with error status for problematic IDs
                        for track_info in track_details:
                            if track_info["track_id"] in problematic_ids:
                                track_info["status"] = "error"
                                if not track_info["error"]:
                                    track_info["error"] = "Invalid track ID detected during batch add"
                        
                        # Return error with full track details using JSONResponse to include track_details
                        error_tracks = [t for t in track_details if t["status"] == "error"]
                        stats = {
                            "total": len(track_details),
                            "added": 0,
                            "skipped": len([t for t in track_details if t["status"] == "skipped"]),
                            "error": len(error_tracks),
                            "valid": 0,
                            "non_track_links": len(skipped_urls)
                        }
                        from fastapi.responses import JSONResponse
                        return JSONResponse(
                            status_code=400,
                            content={
                                "status": "error",
                                "message": f"Found {len(problematic_ids)} invalid track ID(s) that could not be added to playlist.",
                                "track_details": track_details,
                                "skipped_links": skipped_urls,
                                "statistics": stats
                            }
                        )
                    else:
                        # Couldn't identify specific IDs, but we know there's an issue
                        # Update all valid tracks to error status
                        for track_info in track_details:
                            if track_info["status"] == "valid":
                                track_info["status"] = "error"
                                track_info["error"] = f"Batch add failed: {error_msg[:200]}"
                        stats = {
                            "total": len(track_details),
                            "added": 0,
                            "skipped": len([t for t in track_details if t["status"] == "skipped"]),
                            "error": len([t for t in track_details if t["status"] == "error"]),
                            "valid": 0,
                            "non_track_links": len(skipped_urls),
                            "other_links": len(other_links)
                        }
                        from fastapi.responses import JSONResponse
                        return JSONResponse(
                            status_code=400,
                            content={
                                "status": "error",
                                "message": f"Error adding tracks to playlist: {error_msg}",
                                "track_details": track_details,
                                "skipped_links": skipped_urls,
                                "other_links": other_links,
                                "statistics": stats
                            }
                        )
                else:
                    # Re-raise the original error if it's not about invalid IDs
                    # Update all valid tracks to error status
                    for track_info in track_details:
                        if track_info["status"] == "valid":
                            track_info["status"] = "error"
                            track_info["error"] = f"Batch add failed: {error_msg[:200]}"
                    stats = {
                        "total": len(track_details),
                        "added": 0,
                        "skipped": len([t for t in track_details if t["status"] == "skipped"]),
                        "error": len([t for t in track_details if t["status"] == "error"]),
                        "valid": 0
                    }
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": f"Error adding tracks to playlist: {error_msg}",
                            "track_details": track_details,
                            "statistics": stats
                        }
                    )
        else:
            added_count = 0
            logger.info("No new tracks to add (all tracks already in playlist)")
        
        # Count statistics
        stats = {
            "total": len(track_details),
            "added": len([t for t in track_details if t["status"] == "added"]),
            "skipped": len([t for t in track_details if t["status"] == "skipped"]),
            "error": len([t for t in track_details if t["status"] == "error"]),
            "valid": len([t for t in track_details if t["status"] == "valid"]),
            "non_track_links": len(skipped_urls),
            "other_links": len(other_links)
        }
        
        # Store playlist record
        from .database.models import UserPlaylist
        playlist_record = UserPlaylist(
            user_id=current_user.id,
            spotify_playlist_id=playlist['id'],
            playlist_name=playlist_name,
            tracks_count=added_count,
            date_range_start=start_date,
            date_range_end=end_date,
            selected_chats=selected_chat_ids  # Store chat IDs instead of names
        )
        db.add(playlist_record)
        db.commit()
        
        # Determine response status
        skipped_links_msg = ""
        if stats.get("non_track_links", 0) > 0:
            skipped_links_msg = f" ({stats['non_track_links']} non-track Spotify link(s) were skipped - see details below)"
        if stats.get("other_links", 0) > 0:
            other_links_msg = f" ({stats['other_links']} other link(s) found - see details below)"
            skipped_links_msg += other_links_msg
        
        if stats["error"] > 0 and stats["added"] == 0:
            response_status = "error"
            message = f"Failed to add tracks to playlist. {stats['error']} error(s) encountered.{skipped_links_msg}"
        elif stats["error"] > 0:
            response_status = "warning"
            message = f"Playlist '{playlist_name}' created/updated with {stats['added']} track(s), but {stats['error']} track(s) had errors.{skipped_links_msg}"
        elif stats["added"] == 0:
            response_status = "warning"
            message = f"No new tracks added to playlist '{playlist_name}'. {stats['skipped']} track(s) were already in playlist.{skipped_links_msg}"
        else:
            response_status = "success"
            message = f"Playlist '{playlist_name}' created/updated successfully with {stats['added']} track(s).{skipped_links_msg}"
        
        return {
            "status": response_status,
            "message": message,
            "playlist_id": playlist['id'],
            "playlist_url": playlist.get('external_urls', {}).get('spotify'),
            "tracks_added": added_count,
            "total_tracks_found": len(track_urls),
            "track_details": track_details,
            "skipped_links": skipped_urls,  # Non-track Spotify links (albums, playlists, etc.)
            "other_links": other_links,  # All non-Spotify links (Instagram, YouTube, Apple Music, etc.)
            "statistics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating optimized playlist: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error creating playlist: {str(e)}"
        )

@app.post("/create-playlist-optimized-stream")
async def create_playlist_optimized_stream(
    playlist_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    selected_chat_ids: str = Form(...),
    existing_playlist_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create playlist with Server-Sent Events for progress updates.
    Streams progress updates as the playlist is being created.
    """
    async def generate_progress():
        try:
            from .processing.imessage_data_processing.optimized_queries import (
                get_user_db_path, query_messages_with_urls, extract_spotify_urls, extract_all_urls
            )
            from .processing.spotify_interaction import spotify_db_manager as sdm
            from .processing.spotify_interaction import create_spotify_playlist as csp
            import spotipy
            
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
            
            # Get user's database path
            user_data_service = get_user_data_service(db, current_user)
            db_path = get_user_db_path(user_data_service)
            
            if not db_path:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No Messages database found'})}\n\n"
                await asyncio.sleep(0)
                return
            
            # Stage 1: Query messages
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'querying', 'message': 'Querying messages from database...', 'progress': 0})}\n\n"
            await asyncio.sleep(0)  # Allow stream to flush
            messages_df = query_messages_with_urls(db_path, chat_ids, start_date, end_date)
            
            if messages_df.empty:
                yield f"data: {json.dumps({'status': 'warning', 'message': 'No messages with URLs found'})}\n\n"
                await asyncio.sleep(0)
                return
            
            total_messages = len(messages_df)
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'extracting', 'message': f'Found {total_messages} messages. Extracting URLs...', 'progress': 10})}\n\n"
            await asyncio.sleep(0)  # Allow stream to flush
            
            # Stage 2: Extract URLs
            text_column = 'final_text' if 'final_text' in messages_df.columns else 'text'
            url_to_message = {}
            skipped_urls = []
            other_links = []
            
            processed_messages = 0
            update_interval = max(1, total_messages // 20)  # Update ~20 times during extraction
            for idx, row in messages_df.iterrows():
                text = row.get(text_column)
                if pd.notna(text) and text:
                    spotify_urls = extract_spotify_urls(str(text))
                    all_urls = extract_all_urls(str(text))
                    
                    if bool(row.get('is_from_me', False)):
                        sender_name = "You"
                    else:
                        sender_contact = row.get('sender_contact')
                        if pd.notna(sender_contact) and sender_contact:
                            sender_name = str(sender_contact)
                        else:
                            sender_name = row.get('chat_name', 'Unknown Sender')
                    
                    message_info = {
                        "message_text": str(text),
                        "sender_name": sender_name,
                        "is_from_me": bool(row.get('is_from_me', False)),
                        "date": row.get('date_utc', ''),
                        "chat_name": row.get('chat_name', '')
                    }
                    
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
                
                processed_messages += 1
                if processed_messages % update_interval == 0 or processed_messages == total_messages:
                    progress = 10 + int((processed_messages / total_messages) * 20)
                    yield f"data: {json.dumps({'status': 'progress', 'stage': 'extracting', 'message': f'Processed {processed_messages}/{total_messages} messages', 'progress': progress, 'current': processed_messages, 'total': total_messages})}\n\n"
                    await asyncio.sleep(0)  # Allow stream to flush
            
            track_urls = list(url_to_message.keys())
            if not track_urls:
                yield f"data: {json.dumps({'status': 'warning', 'message': 'No Spotify track links found'})}\n\n"
                await asyncio.sleep(0)
                return
            
            yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Found {len(track_urls)} track URLs. Processing tracks...', 'progress': 30})}\n\n"
            await asyncio.sleep(0)  # Allow stream to flush
            
            # Get Spotify tokens
            spotify_tokens = user_data_service.get_spotify_tokens()
            if not spotify_tokens:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Spotify not authorized'})}\n\n"
                await asyncio.sleep(0)
                return
            
            sp = spotipy.Spotify(auth=spotify_tokens.access_token)
            user_id = csp.get_user_id(sp)
            
            # Get or create playlist
            if existing_playlist_id:
                try:
                    playlist = sp.playlist(existing_playlist_id)
                except Exception as e:
                    playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
            else:
                playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
            
            existing_tracks = csp.get_all_playlist_items(sp, playlist['id'])
            existing_track_ids = set(csp.get_song_ids_from_spotify_items(existing_tracks))
            
            # Stage 3: Process each track
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
                        else:
                            track_info["error"] = f"Spotify API error"
                        track_details.append(track_info)
                    
                    processed_tracks += 1
                    progress = 30 + int((processed_tracks / len(track_urls)) * 50)
                    yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Processed {processed_tracks}/{len(track_urls)} tracks', 'progress': progress, 'current': processed_tracks, 'total': len(track_urls)})}\n\n"
                    await asyncio.sleep(0)  # Allow stream to flush
                    
                except Exception as e:
                    track_info["status"] = "error"
                    track_info["error"] = f"Processing error"
                    track_details.append(track_info)
                    processed_tracks += 1
            
            # Stage 4: Add tracks to playlist
            valid_track_ids = [t["track_id"] for t in track_details if t["status"] == "valid"]
            if valid_track_ids:
                yield f"data: {json.dumps({'status': 'progress', 'stage': 'adding', 'message': f'Adding {len(valid_track_ids)} tracks to playlist...', 'progress': 80})}\n\n"
                await asyncio.sleep(0)  # Allow stream to flush
                
                try:
                    # Add in batches
                    batch_size = 100
                    added_count = 0
                    for i in range(0, len(valid_track_ids), batch_size):
                        batch = valid_track_ids[i:i+batch_size]
                        sp.playlist_add_items(playlist['id'], batch)
                        added_count += len(batch)
                        
                        for track_info in track_details:
                            if track_info["track_id"] in batch:
                                track_info["status"] = "added"
                        
                        progress = 80 + int((added_count / len(valid_track_ids)) * 15)
                        yield f"data: {json.dumps({'status': 'progress', 'stage': 'adding', 'message': f'Added {added_count}/{len(valid_track_ids)} tracks', 'progress': progress})}\n\n"
                        await asyncio.sleep(0)  # Allow stream to flush
                    
                    # Count statistics
                    stats = {
                        "total": len(track_details),
                        "added": len([t for t in track_details if t["status"] == "added"]),
                        "skipped": len([t for t in track_details if t["status"] == "skipped"]),
                        "error": len([t for t in track_details if t["status"] == "error"]),
                        "valid": len([t for t in track_details if t["status"] == "valid"]),
                        "non_track_links": len(skipped_urls),
                        "other_links": len(other_links)
                    }
                    
                    # Determine response status
                    skipped_links_msg = ""
                    if stats.get("non_track_links", 0) > 0:
                        skipped_links_msg = f" ({stats['non_track_links']} non-track Spotify link(s) were skipped)"
                    if stats.get("other_links", 0) > 0:
                        skipped_links_msg += f" ({stats['other_links']} other link(s) found)"
                    
                    if stats["error"] > 0 and stats["added"] == 0:
                        response_status = "error"
                        message = f"Failed to add tracks. {stats['error']} error(s) encountered.{skipped_links_msg}"
                    elif stats["error"] > 0:
                        response_status = "warning"
                        message = f"Playlist '{playlist_name}' updated with {stats['added']} track(s), but {stats['error']} track(s) had errors.{skipped_links_msg}"
                    elif stats["added"] == 0:
                        response_status = "warning"
                        message = f"No new tracks added. {stats['skipped']} track(s) were already in playlist.{skipped_links_msg}"
                    else:
                        response_status = "success"
                        message = f"Playlist '{playlist_name}' created/updated successfully with {stats['added']} track(s).{skipped_links_msg}"
                    
                    yield f"data: {json.dumps({'status': 'completed', 'result': {'status': response_status, 'message': message, 'playlist_id': playlist['id'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'tracks_added': stats['added'], 'total_tracks_found': len(track_urls), 'track_details': track_details, 'skipped_links': skipped_urls, 'other_links': other_links, 'statistics': stats}})}\n\n"
                    
                except Exception as e:
                    error_msg = str(e)
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Error adding tracks: {error_msg[:200]}', 'track_details': track_details})}\n\n"
            else:
                yield f"data: {json.dumps({'status': 'warning', 'message': 'No valid tracks to add', 'track_details': track_details})}\n\n"
                
        except Exception as e:
            logger.error(f"Error in playlist creation stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)[:200]}'})}\n\n"
    
    return StreamingResponse(generate_progress(), media_type="text/event-stream")

@app.get("/user-playlists")
async def get_user_playlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of user's Spotify playlists for selection.
    """
    try:
        from .processing.spotify_interaction import create_spotify_playlist as csp
        import spotipy
        
        # Get Spotify tokens
        user_data_service = get_user_data_service(db, current_user)
        spotify_tokens = user_data_service.get_spotify_tokens()
        if not spotify_tokens:
            raise HTTPException(
                status_code=401,
                detail="Spotify not authorized. Please authorize Spotify first."
            )
        
        # Create Spotify client
        sp = spotipy.Spotify(auth=spotify_tokens.access_token)
        
        # Get all playlists (user_playlists can be called without user parameter for current user)
        playlists = []
        try:
            results = sp.current_user_playlists(limit=50)
            logger.info(f"Fetched playlists from Spotify, initial count: {len(results.get('items', []))}")
        except Exception as e:
            logger.error(f"Error fetching playlists from Spotify API: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching playlists from Spotify: {str(e)}"
            )
        
        if not results or 'items' not in results:
            logger.warning("No playlists returned from Spotify API or unexpected response structure")
            return {
                "status": "success",
                "playlists": [],
                "total": 0
            }
        
        while results:
            items = results.get('items', [])
            logger.info(f"Processing {len(items)} playlists from this page")
            
            for playlist in items:
                try:
                    playlists.append({
                        "id": playlist.get('id', ''),
                        "name": playlist.get('name', 'Unnamed Playlist'),
                        "description": playlist.get('description', ''),
                        "tracks_count": playlist.get('tracks', {}).get('total', 0),
                        "public": playlist.get('public', False),
                        "external_url": playlist.get('external_urls', {}).get('spotify', '')
                    })
                except Exception as e:
                    logger.warning(f"Error processing playlist item: {e}")
                    continue
            
            # Handle pagination
            if results.get('next'):
                try:
                    results = sp.next(results)
                except Exception as e:
                    logger.warning(f"Error fetching next page of playlists: {e}")
                    break
            else:
                break
        
        logger.info(f"Total playlists collected: {len(playlists)}")
        
        # Sort by name
        playlists.sort(key=lambda x: x['name'].lower())
        
        return {
            "status": "success",
            "playlists": playlists,
            "total": len(playlists)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user playlists: {e}", exc_info=True)
        error_msg = str(e)
        # Provide more detailed error message
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise HTTPException(
                status_code=401,
                detail="Spotify authorization expired. Please re-authorize Spotify."
            )
        elif "403" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(
                status_code=403,
                detail="Spotify access denied. Please check your Spotify permissions."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Error fetching playlists: {error_msg}"
            )

@app.post("/summary-stats")
async def get_summary_stats(
    chat_ids: str,  # JSON string of chat IDs (integers)
    start_date: str,
    end_date: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate summary statistics for selected chats on-demand.
    Queries all messages (not just Spotify) from selected chats.
    
    Use chat_id instead of chat_name to avoid ambiguity with duplicate chat names.
    """
    try:
        from .processing.imessage_data_processing.optimized_queries import (
            get_user_db_path, query_all_messages_for_stats
        )
        from .processing.imessage_data_processing import data_enrichment as de
        from .processing.contacts_data_processing import import_contact_info as ici
        
        # Parse chat IDs
        try:
            chat_id_list = json.loads(chat_ids) if chat_ids else []
            # Ensure they're integers
            chat_id_list = [int(cid) for cid in chat_id_list]
        except (json.JSONDecodeError, ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail="Invalid chat IDs format. Expected JSON array of chat IDs (integers)."
            )
        
        if not chat_id_list:
            raise HTTPException(
                status_code=400,
                detail="Please select at least one chat."
            )
        
        # Get user's database path
        user_data_service = get_user_data_service(db, current_user)
        db_path = get_user_db_path(user_data_service)
        
        if not db_path:
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please validate username or upload database file first."
            )
        
        # Query all messages for stats using chat_ids
        logger.info(f"Querying all messages from {len(chat_id_list)} chats (by ID) for stats, {start_date} to {end_date}")
        messages_df = query_all_messages_for_stats(db_path, chat_id_list, start_date, end_date)
        
        if messages_df.empty:
            return {
                "status": "warning",
                "message": "No messages found for the selected criteria.",
                "user_stats": []
            }
        
        # Process messages to extract reactions and Spotify links
        # This mimics the enrichment process but only for the selected messages
        messages_df = de.add_reaction_type(messages_df)
        messages_df['extracted_text'] = messages_df['attributedBody'].apply(de.parse_AttributeBody)
        messages_df = de.finalize_text(messages_df)
        messages_df = de.append_links_columns(messages_df, 'final_text')
        
        # Get contacts for name mapping
        contacts = ici.main()
        if contacts is not None and not contacts.empty:
            contacts['phone_number'] = contacts['phone_number'].apply(
                lambda x: '+1' + x if isinstance(x, str) and not x.startswith('+') else x
            )
        else:
            contacts = pd.DataFrame(columns=['phone_number', 'first_name', 'last_name'])
        
        # Compute stats similar to generate_summary_stats.py
        # Group by sender_handle_id
        stats = messages_df.groupby('sender_handle_id').agg(
            messages_sent=('sender_handle_id', 'size'),
            non_reaction_messages=('reaction_type', lambda x: x.eq('no-reaction').sum()),
            loves_sent=('reaction_type', lambda x: x.eq('Loved').sum()),
            likes_sent=('reaction_type', lambda x: x.eq('Liked').sum()),
            hahas_sent=('reaction_type', lambda x: x.eq('Laughed').sum()),
            dislikes_sent=('reaction_type', lambda x: x.eq('Disliked').sum()),
            questions_sent=('reaction_type', lambda x: x.eq('Questioned').sum()),
            emphasized_sent=('reaction_type', lambda x: x.eq('Emphasized').sum()),
            links_sent=('spotify_song_links', lambda x: sum(1 for links in x if isinstance(links, list) and len(links) > 0)),
            first_message_date=('date', 'min'),
            last_message_date=('date', 'max')
        ).fillna(0).reset_index()
        
        # Merge with handle info to get contact_info
        conn_handles = sqlite3.connect(db_path)
        handles_df = pd.read_sql_query(
            "SELECT ROWID as handle_id, id as contact_info FROM handle",
            conn_handles
        )
        conn_handles.close()
        stats = stats.merge(handles_df, left_on='sender_handle_id', right_on='handle_id', how='left')
        
        # Merge with contacts to get names
        if not contacts.empty:
            stats = stats.merge(
                contacts,
                left_on='contact_info',
                right_on='phone_number',
                how='left'
            )
            stats['first_name'] = stats['first_name'].fillna('unknown')
            stats['last_name'] = stats['last_name'].fillna('unknown')
        else:
            stats['first_name'] = 'unknown'
            stats['last_name'] = 'unknown'
        
        # Group by contact_info/name to combine multiple handles for same person
        user_stats = stats.groupby(['contact_info', 'first_name', 'last_name']).agg({
            'messages_sent': 'sum',
            'non_reaction_messages': 'sum',
            'loves_sent': 'sum',
            'likes_sent': 'sum',
            'hahas_sent': 'sum',
            'dislikes_sent': 'sum',
            'questions_sent': 'sum',
            'emphasized_sent': 'sum',
            'links_sent': 'sum',
            'first_message_date': 'min',
            'last_message_date': 'max'
        }).fillna(0).sort_values('messages_sent', ascending=False).reset_index()
        
        # Convert to dict for JSON response
        user_stats_list = user_stats.to_dict('records')
        
        return {
            "status": "success",
            "user_stats": user_stats_list,
            "total_messages": len(messages_df)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating summary stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error generating summary stats: {str(e)}"
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error responses."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "server_error"
        }
    )

# Serve static files (frontend)
# IMPORTANT: This must be AFTER all route definitions to avoid conflicts
# The root route "/" was removed so static files can handle it
try:
    # Check if website directory exists (from packages/dopetracks/ to project root)
    # multiuser_app.py is at: packages/dopetracks/multiuser_app.py
    # website is at: website/ (project root)
    # Need to go up 2 levels: dopetracks -> packages -> root
    current_file_dir = Path(__file__).parent.resolve()
    project_root = current_file_dir.parent.parent
    website_dir = str(project_root / "website")
    if os.path.exists(website_dir) and os.path.isdir(website_dir):
        # Mount static files at root - this will serve index.html for "/"
        app.mount("/", StaticFiles(directory=website_dir, html=True), name="static")
        logger.info(f"Serving static files from: {website_dir}")
    else:
        logger.warning(f"Website directory not found at: {website_dir} - static files not served")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 