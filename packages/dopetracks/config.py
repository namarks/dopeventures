"""
Configuration management for Dopetracks application.
"""
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
# For bundled apps, config is in ~/Library/Application Support/Dopetracks/.env
# For development, config is in project root

# Check if running as bundled app
if getattr(sys, 'frozen', False):
    # Bundled app - use user data directory
    user_data_dir = Path.home() / 'Library' / 'Application Support' / 'Dopetracks'
    env_path = user_data_dir / '.env'
else:
    # Development - use project root
    env_path = Path(__file__).parent.parent.parent / ".env"

if env_path.exists():
    load_dotenv(env_path, override=True)  # override=True ensures .env takes precedence over shell env vars
else:
    # Fallback: try loading from current directory
    load_dotenv(override=True)

class Settings:
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{Path.home() / '.dopetracks' / 'local.db'}"
    )
    
    # Security
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", 
        "dev-secret-key-change-in-production"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # Spotify Configuration
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    # Spotify requires explicit loopback IP (127.0.0.1) instead of localhost
    # See: https://developer.spotify.com/documentation/web-api/concepts/redirect-uri
    SPOTIFY_REDIRECT_URI: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    
    # Validate redirect URI on load - fail fast if misconfigured
    if "localhost" in SPOTIFY_REDIRECT_URI:
        raise ValueError(
            f"SPOTIFY_REDIRECT_URI contains 'localhost' which Spotify doesn't allow. "
            f"Current value: {SPOTIFY_REDIRECT_URI}. "
            f"Must use '127.0.0.1' instead. Update .env file and restart server."
        )
    
    # File Storage
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")  # local, s3, gcs
    STORAGE_BUCKET: Optional[str] = os.getenv("STORAGE_BUCKET")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
    
    # Session Management
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    SESSION_EXPIRE_HOURS: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))
    
    # CORS Settings
    # Include both localhost and 127.0.0.1 for local development
    # Spotify requires 127.0.0.1, but users might access via localhost
    CORS_ORIGINS: list = [
        "http://localhost:8888",  # Main app port
        "http://127.0.0.1:8888",  # Required for Spotify OAuth
        "http://localhost:8889",
        "http://127.0.0.1:8889",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://yourdomain.com"  # Add your production domain
    ]
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return cls.ENVIRONMENT.lower() == "production"
    
    @classmethod
    def validate_required_settings(cls) -> None:
        """Validate that all required settings are present."""
        required_settings = []
        
        if not cls.SPOTIFY_CLIENT_ID:
            required_settings.append("SPOTIFY_CLIENT_ID")
        if not cls.SPOTIFY_CLIENT_SECRET:
            required_settings.append("SPOTIFY_CLIENT_SECRET")
        
        if cls.is_production():
            if cls.SECRET_KEY == "dev-secret-key-change-in-production":
                required_settings.append("SECRET_KEY (production-safe value)")
        
        if required_settings:
            raise ValueError(f"Missing required environment variables: {', '.join(required_settings)}")

# Global settings instance
settings = Settings()

# Validate settings on import (but allow missing settings for setup wizard)
# The setup wizard will run before the main app imports this, so we can be lenient
try:
    settings.validate_required_settings()
except ValueError as e:
    # In development/bundled app, missing settings are OK during setup
    # The launcher will handle setup before importing the app
    if os.getenv("ALLOW_MISSING_SETTINGS", "False").lower() != "true":
        # Only raise if we're not in setup mode
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Missing required settings (this is OK during setup): {e}") 