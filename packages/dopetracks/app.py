"""
FastAPI application for Dopetracks.

Thin entry point — route handlers live in the `routes/` package.
"""
import os
import logging
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the package to Python path for imports
if __name__ == "__main__":
    package_path = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(package_path))

from .config import settings
from .database.connection import init_database, check_database_health
from .utils.helpers import get_db_path
from .routes import (
    spotify_router,
    chats_router,
    playlists_router,
    fts_router,
    system_router,
)
from .routes.helpers import (
    _refresh_prepared_db,
    _periodic_prepared_refresh,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False):
    log_dir = Path.home() / 'Library' / 'Logs' / 'Dopetracks'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'backend.log'
else:
    project_root = Path(__file__).parent.parent.parent.parent
    if (project_root / "packages" / "dopetracks").exists():
        log_file = project_root / "backend.log"
    else:
        log_dir = Path.home() / 'Library' / 'Logs' / 'Dopetracks'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'backend.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting Dopetracks Application")

    async def init_db_async():
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, init_database)
            logger.info("Database initialized successfully")
            health_ok = await loop.run_in_executor(None, check_database_health)
            if not health_ok:
                logger.error("Database health check failed")
                raise RuntimeError("Database is not accessible")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    db_init_task = asyncio.create_task(init_db_async())
    prepared_refresh_task = asyncio.create_task(_periodic_prepared_refresh(300))

    try:
        db_path = get_db_path()
        if db_path and os.path.exists(db_path):
            prepared_db = _refresh_prepared_db(db_path)
            if prepared_db:
                logger.info(f"Prepared DB ready at {prepared_db}")
            else:
                logger.warning("Prepared DB update skipped: ingestion returned no path.")
        else:
            logger.warning("Prepared DB update skipped: Messages database not found.")
    except Exception as e:
        logger.error(f"Error updating prepared DB: {e}", exc_info=True)

    logger.info("Application startup complete (database initializing in background)")
    yield

    try:
        await db_init_task
    except Exception as e:
        logger.warning(f"Database initialization had errors: {e}")
    try:
        prepared_refresh_task.cancel()
        await prepared_refresh_task
    except Exception:
        pass
    logger.info("Application shutdown")


# ---------------------------------------------------------------------------
# App & middleware
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Dopetracks",
    description="Playlist generator from iMessage data",
    version="3.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(system_router)
app.include_router(spotify_router)
app.include_router(chats_router)
app.include_router(playlists_router)
app.include_router(fts_router)
