"""
Session storage service for in-memory data management during user sessions.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import asyncio
from collections import defaultdict

from ..config import settings

logger = logging.getLogger(__name__)

class SessionStorage:
    """In-memory storage for user session data with TTL support."""
    
    def __init__(self, default_ttl_hours: int = None):
        # Dictionary to store user data: {user_id: {data_type: {data: value, timestamp: datetime, ttl_hours: int}}}
        self._storage = defaultdict(dict)
        self._default_ttl_hours = default_ttl_hours or settings.SESSION_EXPIRE_HOURS
        self._cleanup_task = None
        self._cleanup_interval_seconds = 3600  # Run cleanup every hour
    
    def store_data(self, user_id: int, data_type: str, data: Any, ttl_hours: Optional[int] = None) -> None:
        """Store data for a user session with optional TTL."""
        ttl = ttl_hours if ttl_hours is not None else self._default_ttl_hours
        self._storage[user_id][data_type] = {
            'data': data,
            'timestamp': datetime.now(),
            'ttl_hours': ttl
        }
        logger.debug(f"Stored {data_type} data for user {user_id} (TTL: {ttl} hours)")
    
    def get_data(self, user_id: int, data_type: str) -> Optional[Any]:
        """Get data for a user session, checking TTL."""
        if user_id not in self._storage or data_type not in self._storage[user_id]:
            return None
        
        entry = self._storage[user_id][data_type]
        timestamp = entry['timestamp']
        ttl_hours = entry.get('ttl_hours', self._default_ttl_hours)
        
        # Check if data has expired
        if ttl_hours > 0:
            expires_at = timestamp + timedelta(hours=ttl_hours)
            if datetime.now() > expires_at:
                # Data expired, remove it
                del self._storage[user_id][data_type]
                logger.debug(f"Data {data_type} for user {user_id} expired and removed")
                return None
        
        return entry['data']
    
    def clear_user_data(self, user_id: int) -> None:
        """Clear all data for a user session."""
        if user_id in self._storage:
            del self._storage[user_id]
            logger.info(f"Cleared all session data for user {user_id}")
    
    def clear_data_type(self, user_id: int, data_type: str) -> None:
        """Clear specific data type for a user session."""
        if user_id in self._storage and data_type in self._storage[user_id]:
            del self._storage[user_id][data_type]
            logger.debug(f"Cleared {data_type} data for user {user_id}")
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        removed_count = 0
        now = datetime.now()
        
        for user_id in list(self._storage.keys()):
            for data_type in list(self._storage[user_id].keys()):
                entry = self._storage[user_id][data_type]
                timestamp = entry['timestamp']
                ttl_hours = entry.get('ttl_hours', self._default_ttl_hours)
                
                if ttl_hours > 0:
                    expires_at = timestamp + timedelta(hours=ttl_hours)
                    if now > expires_at:
                        del self._storage[user_id][data_type]
                        removed_count += 1
            
            # Remove user entry if no data types remain
            if not self._storage[user_id]:
                del self._storage[user_id]
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired session entries")
        
        return removed_count
    
    async def _periodic_cleanup(self):
        """Periodic cleanup task that runs in the background."""
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval_seconds)
                self.cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Session storage cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in session storage cleanup: {e}")
    
    def start_cleanup_task(self):
        """Start the periodic cleanup task."""
        try:
            loop = asyncio.get_running_loop()
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = loop.create_task(self._periodic_cleanup())
                logger.info("Started session storage cleanup task")
        except RuntimeError:
            # No event loop running, cleanup will be manual only
            logger.warning("No event loop running, session storage cleanup will be manual only")
    
    def stop_cleanup_task(self):
        """Stop the periodic cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Stopped session storage cleanup task")

# Global instance for the application
session_storage = SessionStorage() 