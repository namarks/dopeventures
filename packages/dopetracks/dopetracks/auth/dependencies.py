"""
FastAPI dependencies for authentication and authorization.
"""
from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie, Request
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import User
from .security import get_current_user_from_session

class AuthenticationError(HTTPException):
    """Custom authentication error."""
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class AuthorizationError(HTTPException):
    """Custom authorization error."""
    def __init__(self, detail: str = "Not authorized"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )

def get_session_id_from_cookie(session_id: Optional[str] = Cookie(None, alias="dopetracks_session")) -> Optional[str]:
    """Extract session ID from cookie."""
    return session_id

def get_current_user(
    db: Session = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id_from_cookie)
) -> User:
    """
    Get the current authenticated user.
    Raises 401 if not authenticated.
    """
    if not session_id:
        raise AuthenticationError("No session cookie found")
    
    user = get_current_user_from_session(db, session_id)
    if not user:
        raise AuthenticationError("Invalid or expired session")
    
    if not user.is_active:
        raise AuthenticationError("Account is disabled")
    
    return user

def get_current_user_optional(
    db: Session = Depends(get_db),
    session_id: Optional[str] = Depends(get_session_id_from_cookie)
) -> Optional[User]:
    """
    Get the current authenticated user, but don't raise error if not authenticated.
    Returns None if not authenticated.
    """
    if not session_id:
        return None
    
    user = get_current_user_from_session(db, session_id)
    if not user or not user.is_active:
        return None
    
    return user

def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    # Check for forwarded headers (for reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to client host
    return request.client.host if request.client else "unknown"

def get_user_agent(request: Request) -> str:
    """Get user agent from request."""
    return request.headers.get("User-Agent", "unknown")

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Require admin privileges.
    You can extend the User model to have an is_admin field later.
    """
    # For now, we'll consider the first user as admin
    # In production, add an is_admin field to the User model
    if current_user.id != 1:
        raise AuthorizationError("Admin privileges required")
    
    return current_user 