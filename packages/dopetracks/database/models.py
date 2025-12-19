"""
Database models for Dopetracks application.
"""
import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Optional

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


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # user, admin, super_admin
    permissions = Column(Text)  # JSON array of permission strings
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("UserPasswordReset", back_populates="user", cascade="all, delete-orphan")
    data_caches = relationship("UserDataCache", back_populates="user", cascade="all, delete-orphan")
    uploaded_files = relationship("UserUploadedFile", back_populates="user", cascade="all, delete-orphan")
    spotify_tokens = relationship("UserSpotifyToken", back_populates="user", cascade="all, delete-orphan", uselist=False)
    playlists = relationship("UserPlaylist", back_populates="user", cascade="all, delete-orphan")
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in ["admin", "super_admin"]
    
    def is_super_admin(self) -> bool:
        """Check if user has super admin privileges."""
        return self.role == "super_admin"
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.is_super_admin():
            return True
        if not self.permissions:
            return False
        try:
            user_permissions = json.loads(self.permissions)
            return permission in user_permissions
        except (json.JSONDecodeError, TypeError):
            return False


class UserSession(Base):
    """User session model."""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    ip_address = Column(String(45))  # IPv6 max length
    user_agent = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class UserPasswordReset(Base):
    """Password reset token model."""
    __tablename__ = "user_password_resets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reset_token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="password_resets")


class UserDataCache(Base):
    """User-specific data cache."""
    __tablename__ = "user_data_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    data_type = Column(String(100), nullable=False, index=True)  # e.g., "messages", "contacts", "preferred_db_path"
    data_blob = Column(Text)  # JSON serialized data
    file_hash = Column(String(64))  # SHA256 hash for deduplication
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="data_caches")
    
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class UserUploadedFile(Base):
    """User uploaded file model."""
    __tablename__ = "user_uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    file_hash = Column(String(64), index=True)  # SHA256 hash for deduplication
    storage_path = Column(String(500), nullable=False)
    content_type = Column(String(100), default="application/octet-stream")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="uploaded_files")


class UserSpotifyToken(Base):
    """User-specific Spotify OAuth tokens."""
    __tablename__ = "user_spotify_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime)
    scope = Column(String(500))
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="spotify_tokens")


class UserPlaylist(Base):
    """User-created playlist model."""
    __tablename__ = "user_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    playlist_name = Column(String(255), nullable=False)
    spotify_playlist_id = Column(String(255), index=True)
    track_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="playlists")


# Helper functions
def get_user_by_username(db, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_session(db, session_id: str) -> Optional[User]:
    """Get user by session ID."""
    from datetime import datetime, timezone
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()
    if session:
        return session.user
    return None
