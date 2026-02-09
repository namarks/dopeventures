"""
FTS (Full-Text Search) indexing and status endpoints.
"""
import os
import logging
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..utils.helpers import get_db_path
from .helpers import FTS_AVAILABLE

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fts"])


@router.post("/fts/index")
async def index_fts_database(
    force_rebuild: bool = False,
    db: Session = Depends(get_db)
):
    """Create or update FTS index for Messages database."""
    if not FTS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="FTS indexer not available"
        )

    try:
        from .helpers import get_fts_db_path, populate_fts_database

        db_path = get_db_path()
        if not db_path or not os.path.exists(db_path):
            raise HTTPException(
                status_code=404,
                detail="Messages database not found"
            )

        fts_db_path = get_fts_db_path(db_path)

        logger.info(f"Starting FTS indexing for {db_path} (force_rebuild={force_rebuild})")

        # Run indexing in executor to avoid blocking
        loop = asyncio.get_event_loop()
        stats = await loop.run_in_executor(
            None,
            lambda: populate_fts_database(
                fts_db_path=fts_db_path,
                source_db_path=db_path,
                batch_size=1000,
                force_rebuild=force_rebuild
            )
        )

        return {
            "status": "success",
            "fts_db_path": fts_db_path,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FTS indexing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fts/status")
async def get_fts_index_status(db: Session = Depends(get_db)):
    """Get status of FTS index."""
    if not FTS_AVAILABLE:
        return {"available": False, "reason": "FTS indexer not available"}

    try:
        from .helpers import get_fts_db_path, get_fts_status, is_fts_available

        db_path = get_db_path()
        if not db_path:
            return {"available": False, "reason": "No database path"}

        fts_db_path = get_fts_db_path(db_path)
        available = is_fts_available(fts_db_path)

        if available:
            status = get_fts_status(fts_db_path)
            return {
                "available": True,
                "fts_db_path": fts_db_path,
                "status": status
            }
        else:
            return {
                "available": False,
                "fts_db_path": fts_db_path,
                "reason": "FTS database not found or empty"
            }

    except Exception as e:
        logger.error(f"Error getting FTS status: {e}")
        return {"available": False, "error": str(e)}
