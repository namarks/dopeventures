"""
Authentication and security utilities for Dopetracks.
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import User, UserSession, get_user_by_username, get_user_by_session

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def generate_session_id() -> str:
    """Generate a secure session ID."""
    return secrets.token_urlsafe(32)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_access_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        return None

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user

def create_user_session(
    db: Session, 
    user_id: int, 
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> UserSession:
    """Create a new user session."""
    session_id = generate_session_id()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    
    session = UserSession(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return session

def invalidate_user_session(db: Session, session_id: str) -> bool:
    """Invalidate a user session."""
    session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
    if session:
        db.delete(session)
        db.commit()
        return True
    return False

def get_current_user_from_session(db: Session, session_id: str) -> Optional[User]:
    """Get current user from session ID."""
    return get_user_by_session(db, session_id)

def cleanup_expired_sessions(db: Session) -> int:
    """Remove all expired sessions."""
    count = db.query(UserSession).filter(
        UserSession.expires_at <= datetime.now(timezone.utc)
    ).delete()
    db.commit()
    return count

def hash_file_content(content: bytes) -> str:
    """Generate SHA256 hash of file content for deduplication."""
    return hashlib.sha256(content).hexdigest()

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    # Check for special characters
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is strong"

def generate_secure_filename(original_filename: str, user_id: int) -> str:
    """Generate a secure filename for uploaded files."""
    # Get file extension safely
    if '.' in original_filename:
        ext = original_filename.rsplit('.', 1)[1].lower()
    else:
        ext = 'bin'
    
    # Generate secure filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    random_part = secrets.token_hex(8)
    
    return f"user_{user_id}_{timestamp}_{random_part}.{ext}" 