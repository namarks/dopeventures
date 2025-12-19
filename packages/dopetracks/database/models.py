"""
Database models for Dopetracks application.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class SpotifyToken(Base):
    """Spotify OAuth tokens."""
    __tablename__ = "spotify_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime)
    scope = Column(String(500))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class LocalCache(Base):
    """Local cache for processed data."""
    __tablename__ = "local_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(100), unique=True, index=True, nullable=False)
    data_blob = Column(Text)  # JSON serialized data
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
