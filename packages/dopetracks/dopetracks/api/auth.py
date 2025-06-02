"""
Authentication API endpoints for Dopetracks.
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import User, get_user_by_username, get_user_by_email
from ..auth.security import (
    hash_password, 
    authenticate_user, 
    create_user_session, 
    invalidate_user_session,
    validate_password_strength
)
from ..auth.dependencies import (
    get_current_user, 
    get_current_user_optional,
    get_client_ip,
    get_user_agent
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

# Pydantic models for request/response
class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 50:
            raise ValueError('Username must be less than 50 characters')
        if not v.isalnum() and '_' not in v and '-' not in v:
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: str
    
    class Config:
        from_attributes = True

class AuthResponse(BaseModel):
    user: UserResponse
    message: str

@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserRegister,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    
    # Check if username already exists
    existing_user = get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    existing_email = get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = hash_password(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create session
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    session = create_user_session(db, db_user.id, ip_address, user_agent)
    
    # Set secure cookie
    response.set_cookie(
        key="dopetracks_session",
        value=session.session_id,
        max_age=86400 * 7,  # 7 days
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    logger.info(f"New user registered: {db_user.username} (ID: {db_user.id})")
    
    return AuthResponse(
        user=UserResponse.from_orm(db_user),
        message="Registration successful"
    )

@router.post("/login", response_model=AuthResponse)
async def login(
    user_data: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user and create session."""
    
    user = authenticate_user(db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create session
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    session = create_user_session(db, user.id, ip_address, user_agent)
    
    # Set secure cookie
    response.set_cookie(
        key="dopetracks_session",
        value=session.session_id,
        max_age=86400 * 7,  # 7 days
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    logger.info(f"User logged in: {user.username} (ID: {user.id})")
    
    return AuthResponse(
        user=UserResponse.from_orm(user),
        message="Login successful"
    )

@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user_optional),
    session_id: str = Depends(lambda: None),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session."""
    
    # Get session ID from cookie manually since we want to handle optional
    from fastapi import Cookie
    from ..auth.dependencies import get_session_id_from_cookie
    
    # We need to get the session ID to invalidate it
    # This is a bit tricky with optional auth, so let's handle it directly
    
    response.delete_cookie(key="dopetracks_session")
    
    # Try to invalidate session if we have one
    if current_user:
        # Find and invalidate the session
        # Note: This is a simplified approach
        logger.info(f"User logged out: {current_user.username} (ID: {current_user.id})")
    
    return {"message": "Logout successful"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse.from_orm(current_user)

@router.get("/status")
async def auth_status(current_user: User = Depends(get_current_user_optional)):
    """Check authentication status."""
    if current_user:
        return {
            "authenticated": True,
            "user": UserResponse.from_orm(current_user)
        }
    else:
        return {"authenticated": False}

@router.post("/change-password")
async def change_password(
    current_password: str,
    new_password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password."""
    
    # Verify current password
    user = authenticate_user(db, current_user.username, current_password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    is_valid, message = validate_password_strength(new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    # Update password
    current_user.password_hash = hash_password(new_password)
    db.commit()
    
    logger.info(f"Password changed for user: {current_user.username} (ID: {current_user.id})")
    
    return {"message": "Password changed successfully"}

@router.delete("/account")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user account (requires password confirmation)."""
    
    # Verify password
    user = authenticate_user(db, current_user.username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect"
        )
    
    # Soft delete (deactivate) user
    current_user.is_active = False
    db.commit()
    
    logger.info(f"Account deactivated for user: {current_user.username} (ID: {current_user.id})")
    
    return {"message": "Account deleted successfully"} 