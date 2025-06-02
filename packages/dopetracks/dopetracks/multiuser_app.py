"""
Multi-user FastAPI application for Dopetracks.
Ready for local development and production hosting.
"""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .config import settings
from .database.connection import get_db, init_database, check_database_health
from .database.models import User
from .auth.dependencies import get_current_user, get_current_user_optional
from .services.user_data import get_user_data_service
from .api.auth import router as auth_router

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    
    # Redirect to frontend with success message
    frontend_url = request.url_for("static", path="index.html") if hasattr(request, "url_for") else "/"
    return {"message": "Spotify authorization successful", "redirect": frontend_url}

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
    
    return {
        "has_cached_data": has_messages and has_contacts,
        "messages_cached": has_messages,
        "contacts_cached": has_contacts,
        "is_processing": False  # TODO: Implement processing status tracking
    }

@app.get("/chat-search")
async def chat_search(
    query: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search chats for the current user."""
    user_data_service = get_user_data_service(db, current_user)
    
    # Get cached messages data
    cached_data = user_data_service.get_cached_data("messages")
    if not cached_data:
        raise HTTPException(
            status_code=400, 
            detail="No chat data available. Please upload and process your chat file first."
        )
    
    # TODO: Implement chat search logic here
    # This would use the same logic as the original chat_search but with user's data
    
    return {
        "message": "Chat search endpoint - implementation needed",
        "query": query,
        "user_id": current_user.id
    }

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
        "multiuser_app:app",
        host="0.0.0.0",
        port=8888,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 