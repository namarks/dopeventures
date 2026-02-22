"""
Health, debug, and system endpoints.
"""
import logging
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..database.connection import check_database_health
from ..utils.helpers import get_db_path, validate_db_path
from .helpers import PREPARED_DB_PATH, PREPARED_STATUS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/")
async def read_root():
    """API root endpoint - returns API information."""
    return {
        "name": "Dopetracks API",
        "version": "3.0.0",
        "description": "Playlist generator from iMessage data - Native macOS App",
        "docs": "/docs",
        "health": "/health"
    }


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    db_healthy = check_database_health()
    db_path = get_db_path()

    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "messages_db": "found" if db_path else "not_found",
        "messages_db_path": db_path if db_path else None,
        "environment": "local",
        "version": "3.0.0-local"
    }


@router.get("/prepared-status")
async def prepared_status():
    """Return staleness info for the prepared DB."""
    return {
        "prepared_db_path": PREPARED_DB_PATH,
        "last_prepared_date": PREPARED_STATUS.get("last_prepared_date"),
        "source_max_date": PREPARED_STATUS.get("source_max_date"),
        "staleness_seconds": PREPARED_STATUS.get("staleness_seconds"),
        "last_check_ts": PREPARED_STATUS.get("last_check_ts"),
    }


@router.get("/validate-username")
async def validate_username(username: str):
    """Validate Messages database path for a username."""
    # Strict validation: only allow alphanumeric, hyphens, underscores (prevent path traversal)
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        raise HTTPException(status_code=400, detail="Invalid username: only alphanumeric characters, hyphens, and underscores are allowed")

    db_path = f"/Users/{username}/Library/Messages/chat.db"

    if validate_db_path(db_path):
        return {
            "valid": True,
            "path": db_path,
            "message": "Database found and accessible"
        }
    else:
        return {
            "valid": False,
            "path": db_path,
            "message": "Database not found or not accessible"
        }


@router.get("/open-full-disk-access")
async def open_full_disk_access():
    """Open macOS System Settings to Full Disk Access section."""
    import subprocess
    import platform

    if platform.system() != "Darwin":
        raise HTTPException(status_code=400, detail="This feature is only available on macOS")

    try:
        # Open System Settings to Full Disk Access
        # For macOS Ventura+ (13.0+), use the new URL scheme
        # For older macOS, use the old System Preferences path
        subprocess.run([
            "open",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
        ], check=True)
        return {"success": True, "message": "Opening System Settings to Full Disk Access"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to open System Settings: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to open System Settings. Please open it manually: System Settings > Privacy & Security > Full Disk Access"
        )


@router.get("/debug/contact/{name}")
async def debug_contact(name: str):
    """Debug endpoint to find contact info by name."""
    try:
        sources_dir = Path.home() / "Library/Application Support/AddressBook/Sources"
        if not sources_dir.exists():
            return {"error": "AddressBook Sources directory not found"}

        results = []
        for folder in sources_dir.iterdir():
            potential_db = folder / "AddressBook-v22.abcddb"
            if potential_db.exists():
                conn = sqlite3.connect(str(potential_db))
                cursor = conn.cursor()

                # Search for contact by name
                cursor.execute("""
                    SELECT ZFIRSTNAME, ZLASTNAME, ZUNIQUEID,
                           LENGTH(ZIMAGEDATA) as image_size,
                           LENGTH(ZTHUMBNAILIMAGEDATA) as thumbnail_size,
                           CASE
                               WHEN LENGTH(ZTHUMBNAILIMAGEDATA) < 100 THEN ZTHUMBNAILIMAGEDATA
                               ELSE NULL
                           END as thumbnail_preview
                    FROM ZABCDRECORD
                    WHERE (ZFIRSTNAME LIKE ? OR ZLASTNAME LIKE ? OR (ZFIRSTNAME || ' ' || ZLASTNAME) LIKE ?)
                    LIMIT 10
                """, (f'%{name}%', f'%{name}%', f'%{name}%'))

                rows = cursor.fetchall()
                for row in rows:
                    first_name, last_name, unique_id, image_size, thumbnail_size, thumbnail_preview = row
                    full_name = f"{first_name or ''} {last_name or ''}".strip()

                    # Check if thumbnail is a UUID reference
                    uuid_ref = None
                    if thumbnail_preview and len(thumbnail_preview) < 100:
                        try:
                            uuid_ref = thumbnail_preview.decode('utf-8', errors='ignore')
                            # Strip leading non-printable bytes
                            uuid_ref = uuid_ref.lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')
                            uuid_ref = uuid_ref.strip('\x00').strip()
                        except:
                            pass

                    # Check for external file
                    external_file_exists = False
                    if uuid_ref and '-' in uuid_ref and len(uuid_ref) > 30:
                        external_data_dir = folder / ".AddressBook-v22_SUPPORT" / "_EXTERNAL_DATA"
                        external_file = external_data_dir / uuid_ref
                        external_file_exists = external_file.exists()
                        # Also check if the directory exists
                        if not external_file_exists and external_data_dir.exists():
                            # List files in the directory to see what's there
                            logger.debug(f"External data dir exists but file not found. Dir: {external_data_dir}")

                    results.append({
                        "full_name": full_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "unique_id": unique_id,
                        "image_size": image_size or 0,
                        "thumbnail_size": thumbnail_size or 0,
                        "thumbnail_is_uuid": uuid_ref is not None and '-' in uuid_ref and len(uuid_ref) > 30,
                        "uuid_reference": uuid_ref if uuid_ref and '-' in uuid_ref and len(uuid_ref) > 30 else None,
                        "external_file_exists": external_file_exists,
                        "source_folder": str(folder)
                    })

                conn.close()

        return {
            "search_name": name,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error in debug contact: {e}", exc_info=True)
        return {"error": str(e)}
