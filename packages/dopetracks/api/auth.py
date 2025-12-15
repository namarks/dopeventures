"""
Authentication API endpoints for Dopetracks.
"""
import logging
import secrets
import json
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from ..database.connection import get_db
from ..database.models import User, UserPasswordReset, get_user_by_username, get_user_by_email
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
from ..services.session_storage import session_storage

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
    
    @validator('created_at', pre=True)
    def convert_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True
    
    @classmethod
    def from_user(cls, user):
        """Create UserResponse from User model."""
        return cls.model_validate(user)

class AuthResponse(BaseModel):
    user: UserResponse
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v

@router.get("/")
async def auth_root():
    """Authentication endpoints information."""
    return {
        "message": "Dopetracks Authentication API",
        "endpoints": {
            "POST /auth/register": "Register a new user",
            "POST /auth/login": "Login with username/password",
            "POST /auth/logout": "Logout current user",
            "GET /auth/me": "Get current user info",
            "GET /auth/status": "Check authentication status",
            "POST /auth/change-password": "Change user password",
            "POST /auth/forgot-password": "Request password reset",
            "POST /auth/reset-password": "Reset password with token",
            "GET /auth/verify-reset-token": "Verify password reset token",
            "DELETE /auth/account": "Delete user account",
            "GET /auth/check-username": "Check if username is available"
        },
        "documentation": "/docs"
    }

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
    # Note: Don't set domain - this allows cookie to work for the current hostname
    # For Spotify OAuth, use 127.0.0.1 consistently (not localhost)
    # Using SameSite="lax" for local dev - works for same-site requests
    # For OAuth callback, we use state parameter to pass session ID (more reliable than cookies)
    # In production with HTTPS, can use secure=True with SameSite="lax" or "none"
    response.set_cookie(
        key="dopetracks_session",
        value=session.session_id,
        max_age=86400 * 7,  # 7 days
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",  # Works for same-site requests (127.0.0.1 to 127.0.0.1)
        domain=None,  # Don't set domain - cookie works for current hostname only
        path="/"  # Make cookie available for all paths
    )
    
    logger.info(f"New user registered: {db_user.username} (ID: {db_user.id})")
    
    return AuthResponse(
        user=UserResponse.from_user(db_user),
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
    # #region agent log
    import json
    with open('/Users/nmarks/root_code_repo/dopeventures/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"location":"auth.py:188","message":"login endpoint entry","data":{"username":user_data.username,"hasPassword":bool(user_data.password)},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"})+"\n")
    # #endregion
    
    user = authenticate_user(db, user_data.username, user_data.password)
    
    # #region agent log
    import time
    with open('/Users/nmarks/root_code_repo/dopeventures/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"location":"auth.py:197","message":"authentication result","data":{"authenticated":user is not None,"userId":user.id if user else None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"})+"\n")
    # #endregion
    
    if not user:
        logger.warning(f"Failed login attempt for username: {user_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create session
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    session = create_user_session(db, user.id, ip_address, user_agent)
    
    # #region agent log
    with open('/Users/nmarks/root_code_repo/dopeventures/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"location":"auth.py:210","message":"session created","data":{"sessionId":session.session_id if session else None,"userId":user.id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+"\n")
    # #endregion
    
    # Set secure cookie
    # Note: Don't set domain - this allows cookie to work for the current hostname
    # For Spotify OAuth, use 127.0.0.1 consistently (not localhost)
    # Using SameSite="lax" for local dev - works for same-site requests
    # For OAuth callback, we use state parameter to pass session ID (more reliable than cookies)
    # In production with HTTPS, can use secure=True with SameSite="lax" or "none"
    response.set_cookie(
        key="dopetracks_session",
        value=session.session_id,
        max_age=86400 * 7,  # 7 days
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",  # Works for same-site requests (127.0.0.1 to 127.0.0.1)
        domain=None,  # Don't set domain - cookie works for current hostname only
        path="/"  # Make cookie available for all paths
    )
    
    # #region agent log
    with open('/Users/nmarks/root_code_repo/dopeventures/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"location":"auth.py:225","message":"cookie set","data":{"sessionId":session.session_id},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"})+"\n")
    # #endregion
    
    logger.info(f"User logged in: {user.username} (ID: {user.id})")
    
    auth_response = AuthResponse(
        user=UserResponse.from_user(user),
        message="Login successful"
    )
    
    # #region agent log
    with open('/Users/nmarks/root_code_repo/dopeventures/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"location":"auth.py:231","message":"response prepared","data":{"hasUser":auth_response.user is not None,"userId":auth_response.user.id if auth_response.user else None},"timestamp":int(time.time()*1000),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"})+"\n")
    # #endregion
    
    return auth_response

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log out the current user and clear their session data."""
    try:
        # Clear all session data for the user
        session_storage.clear_user_data(current_user.id)
        
        # Clear any session cookies or tokens here if needed
        
        return {"message": "Successfully logged out"}
    except Exception as e:
        logger.error(f"Error during logout for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred during logout"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse.from_user(current_user)

@router.get("/status")
async def auth_status(current_user: User = Depends(get_current_user_optional)):
    """Check authentication status."""
    if current_user:
        return {
            "authenticated": True,
            "user": UserResponse.from_user(current_user)
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
        logger.warning(f"Failed password change attempt for user: {current_user.username} - incorrect current password")
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

@router.post("/forgot-password")
async def forgot_password(
    request_data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Request a password reset token."""
    
    # Find user by email
    user = get_user_by_email(db, request_data.email)
    if not user:
        # Don't reveal if email exists - return success anyway for security
        logger.info(f"Password reset requested for non-existent email: {request_data.email}")
        return {"message": "If that email address exists, a password reset link has been sent"}
    
    if not user.is_active:
        logger.info(f"Password reset requested for inactive account: {user.email} (ID: {user.id})")
        return {"message": "If that email address exists, a password reset link has been sent"}
    
    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)
    
    # Set expiration (1 hour from now)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Get client info
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # Clean up any existing unused reset tokens for this user
    db.query(UserPasswordReset).filter(
        UserPasswordReset.user_id == user.id,
        UserPasswordReset.used_at.is_(None),
        UserPasswordReset.expires_at > datetime.utcnow()
    ).delete()
    
    # Create new reset token
    reset_record = UserPasswordReset(
        user_id=user.id,
        reset_token=reset_token,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(reset_record)
    db.commit()
    
    # In production, you would send an email here
    # For development, we'll log the reset URL
    reset_url = f"http://localhost:8888/reset-password?token={reset_token}"
    logger.info(f"=== PASSWORD RESET REQUESTED ===")
    logger.info(f"User: {user.username} (ID: {user.id})")
    logger.info(f"Email: {user.email}")
    logger.info(f"IP Address: {ip_address}")
    logger.info(f"User Agent: {user_agent}")
    logger.info(f"Reset Token: {reset_token}")
    logger.info(f"Expires At: {expires_at}")
    logger.info(f"Reset URL (dev only): {reset_url}")
    logger.info(f"===============================")
    
    return {"message": "If that email address exists, a password reset link has been sent"}

@router.get("/verify-reset-token")
async def verify_reset_token(
    token: str = Query(..., description="Password reset token"),
    db: Session = Depends(get_db)
):
    """Verify if a password reset token is valid."""
    
    reset_record = db.query(UserPasswordReset).filter(
        UserPasswordReset.reset_token == token,
        UserPasswordReset.used_at.is_(None),
        UserPasswordReset.expires_at > datetime.utcnow()
    ).first()
    
    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    return {
        "valid": True,
        "user_email": reset_record.user.email,
        "expires_at": reset_record.expires_at.isoformat()
    }

@router.post("/reset-password")
async def reset_password(
    request_data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Reset password using a valid token."""
    
    # Find valid reset token
    reset_record = db.query(UserPasswordReset).filter(
        UserPasswordReset.reset_token == request_data.token,
        UserPasswordReset.used_at.is_(None),
        UserPasswordReset.expires_at > datetime.utcnow()
    ).first()
    
    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    user = reset_record.user
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )
    
    # Update user password
    user.password_hash = hash_password(request_data.new_password)
    user.updated_at = datetime.utcnow()
    
    # Mark reset token as used
    reset_record.used_at = datetime.utcnow()
    
    # Invalidate all existing sessions for security
    from ..database.models import UserSession
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    
    db.commit()
    
    logger.info(f"Password reset completed for user: {user.username} (ID: {user.id})")
    
    return {"message": "Password reset successfully. Please log in with your new password."}

@router.get("/check-username")
async def check_username_availability(
    username: str = Query(..., min_length=3, max_length=50, description="Username to check"),
    db: Session = Depends(get_db)
):
    """Check if a username is available for registration."""
    
    # Validate username format
    username = username.lower()
    if not username.isalnum() and '_' not in username and '-' not in username:
        return {
            "available": False,
            "reason": "Username can only contain letters, numbers, hyphens, and underscores"
        }
    
    # Check if username exists
    existing_user = get_user_by_username(db, username)
    
    if existing_user:
        return {
            "available": False,
            "reason": "Username is already taken"
        }
    else:
        return {
            "available": True,
            "message": "Username is available"
        } 