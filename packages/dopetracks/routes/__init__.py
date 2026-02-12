"""
Route modules for the Dopetracks FastAPI application.
"""
from .spotify import router as spotify_router
from .chats import router as chats_router
from .playlists import router as playlists_router
from .fts import router as fts_router
from .system import router as system_router

__all__ = [
    "spotify_router",
    "chats_router",
    "playlists_router",
    "fts_router",
    "system_router",
]
