"""
Database models for Dopetracks multi-user application.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """User model for authentication and data isolation."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="user")  # user, admin, super_admin
    permissions = Column(Text)  # JSON string of specific permissions
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    spotify_tokens = relationship("UserSpotifyToken", back_populates="user", cascade="all, delete-orphan")
    data_cache = relationship("UserDataCache", back_populates="user", cascade="all, delete-orphan")
    playlists = relationship("UserPlaylist", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("UserPasswordReset", back_populates="user", cascade="all, delete-orphan")

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        if self.role == "super_admin":
            return True
        if self.role == "admin":
            admin_permissions = [
                "view_users", "manage_users", "view_system_stats", 
                "manage_sessions", "view_logs"
            ]
            if permission in admin_permissions:
                return True
        
        # Check custom permissions
        if self.permissions:
            import json
            try:
                custom_perms = json.loads(self.permissions)
                return permission in custom_perms
            except:
                return False
        return False
    
    def is_admin(self) -> bool:
        """Check if user has admin role or higher."""
        return self.role in ["admin", "super_admin"]
    
    def is_super_admin(self) -> bool:
        """Check if user has super admin role."""
        return self.role == "super_admin"

class UserSession(Base):
    """User session model for authentication."""
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(String(500))
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    # Indexes
    __table_args__ = (
        Index('idx_session_user_expires', 'user_id', 'expires_at'),
    )

class UserSpotifyToken(Base):
    """Spotify OAuth tokens per user."""
    __tablename__ = "user_spotify_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime)
    scope = Column(String(500))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="spotify_tokens")

class UserDataCache(Base):
    """Cached processed data per user (messages, contacts, etc.)."""
    __tablename__ = "user_data_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_type = Column(String(50), nullable=False)  # 'messages', 'contacts', 'handles'
    data_blob = Column(Text, nullable=False)  # JSON serialized data
    file_hash = Column(String(64))  # SHA256 hash of source file
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="data_cache")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_data_type', 'user_id', 'data_type'),
    )

class UserUploadedFile(Base):
    """Track uploaded files per user."""
    __tablename__ = "user_uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)  # SHA256
    storage_path = Column(String(500), nullable=False)
    content_type = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_files', 'user_id', 'created_at'),
    )

class UserPlaylist(Base):
    """Track created playlists per user."""
    __tablename__ = "user_playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    spotify_playlist_id = Column(String(100), nullable=False)
    playlist_name = Column(String(255), nullable=False)
    tracks_count = Column(Integer, default=0)
    date_range_start = Column(String(10))  # YYYY-MM-DD
    date_range_end = Column(String(10))    # YYYY-MM-DD
    selected_chats = Column(Text)  # JSON array of chat names
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="playlists")
    
    # Indexes
    __table_args__ = (
        Index('idx_user_playlists', 'user_id', 'created_at'),
    )

class UserPasswordReset(Base):
    """Password reset tokens for users."""
    __tablename__ = "user_password_resets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reset_token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    ip_address = Column(String(45))  # Track where reset was requested
    user_agent = Column(String(500))
    
    # Relationships
    user = relationship("User", back_populates="password_resets")
    
    # Indexes
    __table_args__ = (
        Index('idx_reset_token_expires', 'reset_token', 'expires_at'),
        Index('idx_user_resets', 'user_id', 'created_at'),
    )

# Utility functions for models
def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Get user by username."""
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email."""
    return db.query(User).filter(User.email == email).first()

def get_user_by_session(db: Session, session_id: str) -> Optional[User]:
    """Get user by active session ID."""
    session = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()
    
    return session.user if session else None

def cleanup_expired_sessions(db: Session) -> int:
    """Remove expired sessions and return count of deleted sessions."""
    result = db.query(UserSession).filter(
        UserSession.expires_at <= datetime.now(timezone.utc)
    ).delete()
    db.commit()
    return result 