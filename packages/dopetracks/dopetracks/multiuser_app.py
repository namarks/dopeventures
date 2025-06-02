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
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv

# Add the package to Python path for imports
if __name__ == "__main__":
    package_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(package_path))

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
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
load_dotenv()

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

@app.get("/")
async def root(current_user: User = Depends(get_current_user_optional)):
    """Root endpoint."""
    if current_user:
        return {
            "message": f"Welcome to Dopetracks, {current_user.username}!",
            "authenticated": True,
            "user_id": current_user.id
        }
    else:
        return {
            "message": "Welcome to Dopetracks Multi-User",
            "authenticated": False,
            "login_url": "/auth/login",
            "register_url": "/auth/register"
        }

# Spotify OAuth endpoints (adapted for multi-user)
@app.get("/get-client-id")
async def get_client_id():
    """Get Spotify client ID for OAuth."""
    if not settings.SPOTIFY_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Spotify client ID not configured")
    
    return {"client_id": settings.SPOTIFY_CLIENT_ID}

@app.get("/callback")
async def spotify_callback(
    request: Request,
    code: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Handle Spotify OAuth callback."""
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")
    
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
    
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(
            status_code=400, 
            detail="Failed to exchange authorization code for tokens"
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
            // Redirect to main app after 2 seconds
            setTimeout(function() {
                window.location.href = '/index.html';
            }, 2000);
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
        raise HTTPException(status_code=401, detail="Spotify not authorized")
    
    import requests
    headers = {"Authorization": f"Bearer {spotify_tokens.access_token}"}
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    
    if response.status_code != 200:
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
    """Server-Sent Events endpoint for real-time progress updates during data preparation."""
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search chats for the current user."""
    user_data_service = get_user_data_service(db, current_user)
    
    # Get cached messages data
    messages_data = user_data_service.get_cached_data("messages")
    contacts_data = user_data_service.get_cached_data("contacts")
    
    if messages_data is None:
        raise HTTPException(
            status_code=400, 
            detail="No chat data available. Please complete data preparation first."
        )
    
    try:
        import pandas as pd
        
        # Deserialize DataFrame data if it's in the new format
        if isinstance(messages_data, dict) and messages_data.get("_type") == "dataframe":
            messages_df = deserialize_dataframe(messages_data["_data"])
        else:
            # Handle legacy or other formats
            logger.warning("Cached data is not in expected DataFrame format")
            return []
        
        if isinstance(contacts_data, dict) and contacts_data.get("_type") == "dataframe":
            contacts_df = deserialize_dataframe(contacts_data["_data"])
        else:
            contacts_df = None
        
        # Create contacts lookup if available
        contacts_lookup = {}
        if contacts_df is not None:
            for _, contact in contacts_df.iterrows():
                phone = contact.get('phone_number', '')
                first_name = contact.get('first_name', '')
                last_name = contact.get('last_name', '')
                if phone:
                    full_name = f"{first_name} {last_name}".strip()
                    if full_name:
                        contacts_lookup[phone] = full_name
        
        # Get unique chats with their participant info
        chat_info = messages_df.groupby('chat_name').agg({
            'chat_members_contact_info': 'first',  # Get participant contact info
            'sender_handle_id': 'nunique',  # Number of unique senders (members)
            'message_id': 'count',  # Total messages in this chat
            'spotify_song_links': lambda x: sum(len(links) for links in x if isinstance(links, list))
        }).reset_index()
        
        # Search in chat names and participant names
        query_lower = query.lower()
        matching_chats = []
        
        for _, chat in chat_info.iterrows():
            chat_name = str(chat['chat_name']) if chat['chat_name'] else ""
            chat_members_str = str(chat['chat_members_contact_info']) if chat['chat_members_contact_info'] else ""
            
            # Check if query matches chat name
            name_match = query_lower in chat_name.lower()
            
            # Check if query matches any participant names
            participant_match = False
            if chat_members_str:
                # Parse the contact info (usually phone numbers separated by commas)
                contact_infos = [info.strip() for info in chat_members_str.split(',')]
                for contact_info in contact_infos:
                    # Check if we have a name for this contact
                    if contact_info in contacts_lookup:
                        participant_name = contacts_lookup[contact_info].lower()
                        if query_lower in participant_name:
                            participant_match = True
                            break
                    # Also check the contact info itself (phone number)
                    elif query_lower in contact_info.lower():
                        participant_match = True
                        break
            
            if name_match or participant_match:
                # Build participant names list for display
                participant_names = []
                if chat_members_str:
                    contact_infos = [info.strip() for info in chat_members_str.split(',')]
                    for contact_info in contact_infos:
                        if contact_info in contacts_lookup:
                            participant_names.append(contacts_lookup[contact_info])
                        else:
                            participant_names.append(contact_info)
                
                matching_chats.append({
                    'chat_name': chat_name,
                    'participant_count': int(chat['sender_handle_id']),
                    'message_count': int(chat['message_id']),
                    'spotify_links_count': int(chat['spotify_song_links']),
                    'participants': participant_names[:5],  # Limit to first 5 for display
                    'match_type': 'name' if name_match else 'participant'
                })
        
        # Sort by message count (most active chats first)
        matching_chats.sort(key=lambda x: x['message_count'], reverse=True)
        
        logger.info(f"Found {len(matching_chats)} matching chats for query '{query}'")
        return matching_chats[:20]  # Limit to top 20 results
        
    except Exception as e:
        logger.error(f"Error in chat search: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

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

# Serve static files (frontend) - only in development
if not settings.is_production():
    try:
        # Check if website directory exists
        website_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "website")
        if os.path.exists(website_dir):
            app.mount("/", StaticFiles(directory=website_dir, html=True), name="static")
            logger.info("Serving static files from website directory")
        else:
            logger.warning("Website directory not found - static files not served")
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