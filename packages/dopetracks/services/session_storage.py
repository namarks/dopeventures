"""
Session storage service for in-memory data management during user sessions.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class SessionStorage:
    """In-memory storage for user session data."""
    
    def __init__(self):
        # Dictionary to store user data: {user_id: {data_type: {data: value, timestamp: datetime}}}
        self._storage = defaultdict(dict)
    
    def store_data(self, user_id: int, data_type: str, data: Any) -> None:
        """Store data for a user session."""
        self._storage[user_id][data_type] = {
            'data': data,
            'timestamp': datetime.now()
        }
        logger.info(f"Stored {data_type} data for user {user_id}")
    
    def get_data(self, user_id: int, data_type: str) -> Optional[Any]:
        """Get data for a user session."""
        if user_id in self._storage and data_type in self._storage[user_id]:
            return self._storage[user_id][data_type]['data']
        return None
    
    def clear_user_data(self, user_id: int) -> None:
        """Clear all data for a user session."""
        if user_id in self._storage:
            del self._storage[user_id]
            logger.info(f"Cleared all session data for user {user_id}")
    
    def clear_data_type(self, user_id: int, data_type: str) -> None:
        """Clear specific data type for a user session."""
        if user_id in self._storage and data_type in self._storage[user_id]:
            del self._storage[user_id][data_type]
            logger.info(f"Cleared {data_type} data for user {user_id}")

# Global instance for the application
session_storage = SessionStorage() 