"""
Configuration management for Dopetracks application.
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# Bundled apps: ~/Library/Application Support/Dopetracks/.env
# Development:  project root .env
if getattr(sys, 'frozen', False):
    user_data_dir = Path.home() / 'Library' / 'Application Support' / 'Dopetracks'
    env_path = user_data_dir / '.env'
else:
    env_path = Path(__file__).parent.parent.parent / ".env"

if env_path.exists():
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)


class Settings:
    """Application settings loaded from environment variables."""

    # Database (local SQLite)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{Path.home() / '.dopetracks' / 'local.db'}"
    )

    # Spotify Configuration
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    # Spotify requires 127.0.0.1, not localhost
    if "localhost" in SPOTIFY_REDIRECT_URI:
        raise ValueError(
            f"SPOTIFY_REDIRECT_URI contains 'localhost' which Spotify doesn't allow. "
            f"Current value: {SPOTIFY_REDIRECT_URI}. "
            f"Must use '127.0.0.1' instead. Update .env file and restart."
        )

    # CORS (local only)
    CORS_ORIGINS: list = [
        "http://127.0.0.1:8888",
        "http://localhost:8888",
    ]

    # Logging
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate_required_settings(cls) -> None:
        """Validate that Spotify credentials are configured."""
        missing = []
        if not cls.SPOTIFY_CLIENT_ID:
            missing.append("SPOTIFY_CLIENT_ID")
        if not cls.SPOTIFY_CLIENT_SECRET:
            missing.append("SPOTIFY_CLIENT_SECRET")
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


# Global settings instance
settings = Settings()

# Validate on import (warn only — setup wizard may run first)
try:
    settings.validate_required_settings()
except ValueError as e:
    if os.getenv("ALLOW_MISSING_SETTINGS", "False").lower() != "true":
        logger = logging.getLogger(__name__)
        logger.warning(f"Missing settings (OK during setup): {e}")
