"""
Admin API endpoints for user and system management.
"""
import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..database.connection import get_db
from ..database.models import User, UserSession, UserPlaylist, UserUploadedFile, UserDataCache
from ..auth.dependencies import require_admin, require_super_admin, require_permission, get_current_user
from ..auth.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Pydantic models
class UserSummary(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None
    playlist_count: int = 0
    
    @validator('created_at', pre=True)
    def convert_datetime(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    @validator('last_login', pre=True)
    def convert_last_login(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    users: List[UserSummary]
    total: int
    page: int
    per_page: int
    total_pages: int

class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_admins: int
    total_playlists: int
    total_uploads: int
    active_sessions: int
    storage_used: int  # bytes
    uptime: str

class UserRoleUpdate(BaseModel):
    role: str
    permissions: Optional[List[str]] = None
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ["user", "admin", "super_admin"]:
            raise ValueError("Role must be one of: user, admin, super_admin")
        return v

class CreateAdminUser(BaseModel):
    username: str
    email: str
    password: str
    role: str = "admin"
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ["admin", "super_admin"]:
            raise ValueError("Role must be admin or super_admin")
        return v

# Admin endpoints
@router.get("/")
async def admin_root():
    """Admin endpoints information."""
    return {
        "message": "Dopetracks Admin API",
        "endpoints": {
            "GET /admin/users": "List all users (admin)",
            "GET /admin/users/{user_id}": "Get user details (admin)",
            "PUT /admin/users/{user_id}/role": "Update user role (super_admin)",
            "DELETE /admin/users/{user_id}": "Delete user (super_admin)",
            "POST /admin/users": "Create admin user (super_admin)",
            "GET /admin/stats": "System statistics (admin)",
            "GET /admin/sessions": "Active sessions (admin)",
            "DELETE /admin/sessions/{session_id}": "Terminate session (admin)",
            "GET /admin/logs": "System logs (admin)"
        },
        "permissions": {
            "admin": ["view_users", "manage_users", "view_system_stats", "manage_sessions", "view_logs"],
            "super_admin": ["all_permissions"]
        }
    }

@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_users"))
):
    """List all users with pagination and filtering."""
    query = db.query(User)
    
    # Apply filters
    if role:
        query = query.filter(User.role == role)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_term)) | 
            (User.email.ilike(search_term))
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.order_by(desc(User.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    
    # Get additional data for each user
    user_summaries = []
    for user in users:
        # Get last login from sessions
        last_session = db.query(UserSession).filter(
            UserSession.user_id == user.id
        ).order_by(desc(UserSession.created_at)).first()
        
        # Get playlist count
        playlist_count = db.query(UserPlaylist).filter(
            UserPlaylist.user_id == user.id
        ).count()
        
        user_summary = UserSummary(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=last_session.created_at if last_session else None,
            playlist_count=playlist_count
        )
        user_summaries.append(user_summary)
    
    total_pages = (total + per_page - 1) // per_page
    
    return UserListResponse(
        users=user_summaries,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )

@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_users"))
):
    """Get detailed user information."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user statistics
    playlist_count = db.query(UserPlaylist).filter(UserPlaylist.user_id == user_id).count()
    upload_count = db.query(UserUploadedFile).filter(UserUploadedFile.user_id == user_id).count()
    active_sessions = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.expires_at > datetime.utcnow()
    ).count()
    
    # Get recent sessions
    recent_sessions = db.query(UserSession).filter(
        UserSession.user_id == user_id
    ).order_by(desc(UserSession.created_at)).limit(5).all()
    
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "permissions": json.loads(user.permissions) if user.permissions else [],
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        },
        "statistics": {
            "playlist_count": playlist_count,
            "upload_count": upload_count,
            "active_sessions": active_sessions
        },
        "recent_sessions": [
            {
                "id": session.id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
                "ip_address": session.ip_address,
                "user_agent": session.user_agent[:100] + "..." if len(session.user_agent) > 100 else session.user_agent
            }
            for session in recent_sessions
        ]
    }

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Update user role and permissions (super admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow demoting yourself
    if user.id == current_user.id and role_update.role != "super_admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    
    # Update role
    old_role = user.role
    user.role = role_update.role
    
    # Update permissions
    if role_update.permissions:
        user.permissions = json.dumps(role_update.permissions)
    else:
        user.permissions = None
    
    user.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        logger.info(f"User {user.username} (ID: {user.id}) role updated from {old_role} to {role_update.role} by {current_user.username}")
        
        return {
            "message": f"User role updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "permissions": json.loads(user.permissions) if user.permissions else []
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update user role: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user role")

@router.post("/users")
async def create_admin_user(
    user_data: CreateAdminUser,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Create a new admin user (super admin only)."""
    # Check if username or email already exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already exists")
    
    # Create new admin user
    password_hash = hash_password(user_data.password)
    
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=password_hash,
        role=user_data.role,
        is_active=True
    )
    
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"New {user_data.role} user created: {user_data.username} (ID: {new_user.id}) by {current_user.username}")
        
        return {
            "message": f"{user_data.role.title()} user created successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role,
                "created_at": new_user.created_at.isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create admin user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("view_system_stats"))
):
    """Get system statistics."""
    # Count users
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_admins = db.query(User).filter(User.role.in_(["admin", "super_admin"])).count()
    
    # Count resources
    total_playlists = db.query(UserPlaylist).count()
    total_uploads = db.query(UserUploadedFile).count()
    
    # Active sessions
    active_sessions = db.query(UserSession).filter(
        UserSession.expires_at > datetime.utcnow()
    ).count()
    
    # Storage used (approximate)
    storage_result = db.query(func.sum(UserUploadedFile.file_size)).scalar()
    storage_used = storage_result or 0
    
    # Simple uptime (time since first user created)
    first_user = db.query(User).order_by(User.created_at).first()
    if first_user:
        uptime_delta = datetime.utcnow() - first_user.created_at
        uptime = f"{uptime_delta.days} days, {uptime_delta.seconds // 3600} hours"
    else:
        uptime = "No data"
    
    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_admins=total_admins,
        total_playlists=total_playlists,
        total_uploads=total_uploads,
        active_sessions=active_sessions,
        storage_used=storage_used,
        uptime=uptime
    )

@router.get("/sessions")
async def list_active_sessions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_sessions"))
):
    """List active sessions."""
    query = db.query(UserSession).filter(
        UserSession.expires_at > datetime.utcnow()
    ).join(User)
    
    total = query.count()
    sessions = query.order_by(desc(UserSession.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    
    session_list = []
    for session in sessions:
        session_list.append({
            "id": session.id,
            "session_id": session.session_id[:16] + "...",  # Partial for security
            "user": {
                "id": session.user.id,
                "username": session.user.username,
                "role": session.user.role
            },
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "ip_address": session.ip_address,
            "user_agent": session.user_agent[:50] + "..." if len(session.user_agent) > 50 else session.user_agent
        })
    
    total_pages = (total + per_page - 1) // per_page
    
    return {
        "sessions": session_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }

@router.delete("/sessions/{db_session_id}")
async def terminate_session(
    db_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("manage_sessions"))
):
    """Terminate a user session."""
    session = db.query(UserSession).filter(UserSession.id == db_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Don't allow terminating your own session
    if session.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot terminate your own session")
    
    try:
        db.delete(session)
        db.commit()
        
        logger.info(f"Session {session.session_id} for user {session.user.username} terminated by {current_user.username}")
        
        return {"message": "Session terminated successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to terminate session: {e}")
        raise HTTPException(status_code=500, detail="Failed to terminate session")

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete a user and all their data (super admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    username = user.username
    
    try:
        # SQLAlchemy will handle cascade deletes for related records
        db.delete(user)
        db.commit()
        
        logger.warning(f"User {username} (ID: {user_id}) deleted by {current_user.username}")
        
        return {"message": f"User {username} deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user") 