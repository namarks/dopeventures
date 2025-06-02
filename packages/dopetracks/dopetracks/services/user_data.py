"""
User data management service for per-user data isolation.
"""
import json
import logging
import os
import hashlib
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from ..database.models import (
    User, UserDataCache, UserUploadedFile, UserSpotifyToken
)
from ..auth.security import hash_file_content, generate_secure_filename
from ..config import settings

logger = logging.getLogger(__name__)

class UserDataService:
    """Service for managing user-specific data."""
    
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
    
    def get_cached_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        """Get cached data for a specific type (messages, contacts, etc.)."""
        cache_entry = self.db.query(UserDataCache).filter(
            UserDataCache.user_id == self.user.id,
            UserDataCache.data_type == data_type
        ).first()
        
        if cache_entry:
            try:
                return json.loads(cache_entry.data_blob)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode cached data for user {self.user.id}, type {data_type}")
                return None
        
        return None
    
    def set_cached_data(
        self, 
        data_type: str, 
        data: Dict[str, Any], 
        file_hash: Optional[str] = None
    ) -> bool:
        """Set cached data for a specific type."""
        try:
            data_blob = json.dumps(data, default=str)  # default=str for datetime serialization
            
            # Check if entry exists
            cache_entry = self.db.query(UserDataCache).filter(
                UserDataCache.user_id == self.user.id,
                UserDataCache.data_type == data_type
            ).first()
            
            if cache_entry:
                # Update existing entry
                cache_entry.data_blob = data_blob
                cache_entry.file_hash = file_hash
            else:
                # Create new entry
                cache_entry = UserDataCache(
                    user_id=self.user.id,
                    data_type=data_type,
                    data_blob=data_blob,
                    file_hash=file_hash
                )
                self.db.add(cache_entry)
            
            self.db.commit()
            logger.info(f"Cached data updated for user {self.user.id}, type {data_type}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache data for user {self.user.id}, type {data_type}: {e}")
            self.db.rollback()
            return False
    
    def clear_cached_data(self, data_type: Optional[str] = None) -> bool:
        """Clear cached data. If data_type is None, clear all cached data for user."""
        try:
            query = self.db.query(UserDataCache).filter(
                UserDataCache.user_id == self.user.id
            )
            
            if data_type:
                query = query.filter(UserDataCache.data_type == data_type)
            
            deleted_count = query.delete()
            self.db.commit()
            
            logger.info(f"Cleared {deleted_count} cached data entries for user {self.user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear cached data for user {self.user.id}: {e}")
            self.db.rollback()
            return False
    
    def save_uploaded_file(
        self, 
        file_content: bytes, 
        original_filename: str,
        content_type: str = "application/octet-stream"
    ) -> Optional[UserUploadedFile]:
        """Save an uploaded file for the user."""
        try:
            # Generate file hash for deduplication
            file_hash = hash_file_content(file_content)
            
            # Check if file already exists for this user
            existing_file = self.db.query(UserUploadedFile).filter(
                UserUploadedFile.user_id == self.user.id,
                UserUploadedFile.file_hash == file_hash
            ).first()
            
            if existing_file:
                logger.info(f"File already exists for user {self.user.id}: {existing_file.filename}")
                return existing_file
            
            # Generate secure filename
            secure_filename = generate_secure_filename(original_filename, self.user.id)
            
            # Create storage directory
            if settings.STORAGE_TYPE == "local":
                storage_dir = f"./user_uploads/user_{self.user.id}"
                os.makedirs(storage_dir, exist_ok=True)
                storage_path = os.path.join(storage_dir, secure_filename)
                
                # Write file to disk
                with open(storage_path, "wb") as f:
                    f.write(file_content)
            else:
                # For cloud storage, implement S3/GCS upload here
                storage_path = f"user_{self.user.id}/{secure_filename}"
                # TODO: Implement cloud storage upload
                logger.warning("Cloud storage not implemented yet")
            
            # Create database entry
            uploaded_file = UserUploadedFile(
                user_id=self.user.id,
                filename=secure_filename,
                original_filename=original_filename,
                file_size=len(file_content),
                file_hash=file_hash,
                storage_path=storage_path,
                content_type=content_type
            )
            
            self.db.add(uploaded_file)
            self.db.commit()
            self.db.refresh(uploaded_file)
            
            logger.info(f"File saved for user {self.user.id}: {secure_filename}")
            return uploaded_file
            
        except Exception as e:
            logger.error(f"Failed to save file for user {self.user.id}: {e}")
            self.db.rollback()
            return None
    
    def get_uploaded_files(self) -> List[UserUploadedFile]:
        """Get all uploaded files for the user."""
        return self.db.query(UserUploadedFile).filter(
            UserUploadedFile.user_id == self.user.id
        ).order_by(UserUploadedFile.created_at.desc()).all()
    
    def get_file_content(self, file_id: int) -> Optional[bytes]:
        """Get the content of an uploaded file."""
        uploaded_file = self.db.query(UserUploadedFile).filter(
            UserUploadedFile.id == file_id,
            UserUploadedFile.user_id == self.user.id
        ).first()
        
        if not uploaded_file:
            return None
        
        try:
            if settings.STORAGE_TYPE == "local":
                with open(uploaded_file.storage_path, "rb") as f:
                    return f.read()
            else:
                # TODO: Implement cloud storage download
                logger.warning("Cloud storage download not implemented yet")
                return None
                
        except Exception as e:
            logger.error(f"Failed to read file {file_id} for user {self.user.id}: {e}")
            return None
    
    def delete_uploaded_file(self, file_id: int) -> bool:
        """Delete an uploaded file."""
        uploaded_file = self.db.query(UserUploadedFile).filter(
            UserUploadedFile.id == file_id,
            UserUploadedFile.user_id == self.user.id
        ).first()
        
        if not uploaded_file:
            return False
        
        try:
            # Delete from storage
            if settings.STORAGE_TYPE == "local":
                if os.path.exists(uploaded_file.storage_path):
                    os.remove(uploaded_file.storage_path)
            else:
                # TODO: Implement cloud storage deletion
                pass
            
            # Delete from database
            self.db.delete(uploaded_file)
            self.db.commit()
            
            logger.info(f"File deleted for user {self.user.id}: {uploaded_file.filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id} for user {self.user.id}: {e}")
            self.db.rollback()
            return False
    
    def store_spotify_tokens(
        self, 
        access_token: str, 
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        scope: Optional[str] = None
    ) -> bool:
        """Store Spotify OAuth tokens for the user."""
        try:
            from datetime import datetime, timedelta, timezone
            
            expires_at = None
            if expires_in:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Check if tokens already exist
            token_entry = self.db.query(UserSpotifyToken).filter(
                UserSpotifyToken.user_id == self.user.id
            ).first()
            
            if token_entry:
                # Update existing tokens
                token_entry.access_token = access_token
                if refresh_token:
                    token_entry.refresh_token = refresh_token
                token_entry.expires_at = expires_at
                token_entry.scope = scope
            else:
                # Create new token entry
                token_entry = UserSpotifyToken(
                    user_id=self.user.id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    scope=scope
                )
                self.db.add(token_entry)
            
            self.db.commit()
            logger.info(f"Spotify tokens stored for user {self.user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store Spotify tokens for user {self.user.id}: {e}")
            self.db.rollback()
            return False
    
    def get_spotify_tokens(self) -> Optional[UserSpotifyToken]:
        """Get Spotify OAuth tokens for the user."""
        return self.db.query(UserSpotifyToken).filter(
            UserSpotifyToken.user_id == self.user.id
        ).first()
    
    def clear_spotify_tokens(self) -> bool:
        """Clear Spotify OAuth tokens for the user."""
        try:
            deleted_count = self.db.query(UserSpotifyToken).filter(
                UserSpotifyToken.user_id == self.user.id
            ).delete()
            
            self.db.commit()
            logger.info(f"Cleared Spotify tokens for user {self.user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear Spotify tokens for user {self.user.id}: {e}")
            self.db.rollback()
            return False

def get_user_data_service(db: Session, user: User) -> UserDataService:
    """Factory function to create UserDataService instance."""
    return UserDataService(db, user) 