"""
Configuration management for Dopetracks multi-user application.
Supports both local development and production hosting.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv()

class Settings:
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./dopetracks_multiuser.db"
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
    SPOTIFY_REDIRECT_URI: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    
    # File Storage
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "local")  # local, s3, gcs
    STORAGE_BUCKET: Optional[str] = os.getenv("STORAGE_BUCKET")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
    
    # Session Management
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    SESSION_EXPIRE_HOURS: int = int(os.getenv("SESSION_EXPIRE_HOURS", "24"))
    
    # CORS Settings
    CORS_ORIGINS: list = [
        "http://localhost:8889",
        "http://localhost:3000",
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

# Validate settings on import
settings.validate_required_settings() 