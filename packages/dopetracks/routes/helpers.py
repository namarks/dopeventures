"""
Shared helper functions and global state used across route modules.
"""
import os
import logging
import asyncio
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database.models import SpotifyToken
from ..utils.helpers import get_db_path, validate_db_path
from ..processing.imessage_data_processing.prepared_messages import (
    chat_search_prepared,
    get_last_processed_date,
)
from ..processing.contacts_data_processing.import_contact_info import (
    get_contact_info_by_handle,
)
from ..processing.imessage_data_processing.handle_utils import (
    normalize_handle,
    normalize_handle_variants,
)
from ..processing.imessage_data_processing.ingestion import ingest_prepared_store, get_source_max_date

logger = logging.getLogger(__name__)

# Simple in-memory TTL cache for chat list
CHAT_CACHE_TTL_SECONDS = 30
_chat_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
# Path to prepared DB (populated via ingestion)
PREPARED_DB_PATH: Optional[str] = None
PREPARED_STATUS: Dict[str, Any] = {
    "last_prepared_date": None,
    "source_max_date": None,
    "staleness_seconds": None,
    "last_check_ts": None,
}

# FTS indexer imports
try:
    from ..processing.imessage_data_processing.fts_indexer import (
        get_fts_db_path,
        populate_fts_database,
        get_fts_status,
        is_fts_available
    )
    FTS_AVAILABLE = True
except ImportError:
    FTS_AVAILABLE = False
    logger.warning("FTS indexer not available - will use fallback search method")


def _refresh_prepared_db(source_db_path: str, force_rebuild: bool = False) -> Optional[str]:
    """Run incremental ingestion and update global prepared DB path."""
    global PREPARED_DB_PATH, _chat_cache
    result = ingest_prepared_store(
        source_db_path=source_db_path,
        base_dir=None,
        force_rebuild=force_rebuild,
    )
    prepared_db_path = result.get("prepared_db_path")
    if prepared_db_path and prepared_db_path != PREPARED_DB_PATH:
        _chat_cache.clear()
    if prepared_db_path:
        PREPARED_DB_PATH = prepared_db_path
    return PREPARED_DB_PATH


def _parse_naive_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str or dt_str == "0":
        return None
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None


def _compute_staleness_seconds(source_dt: Optional[str], prepared_dt: Optional[str]) -> Optional[int]:
    src = _parse_naive_dt(source_dt)
    prep = _parse_naive_dt(prepared_dt)
    if not src or not prep:
        return None
    delta = (src - prep).total_seconds()
    return int(delta) if delta > 0 else 0


def _resolve_sender_name_from_prepared(prepared_db: str, sender_handle: Optional[str]) -> Optional[Dict[str, Any]]:
    if not sender_handle:
        return None
    variants = normalize_handle_variants(sender_handle)
    if not variants:
        return None
    try:
        conn = sqlite3.connect(prepared_db)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(variants))
        cur.execute(
            f"""
            SELECT contact_info, display_name
            FROM contacts
            WHERE contact_info IN ({placeholders})
            LIMIT 1
            """,
            variants,
        )
        row = cur.fetchone()
        conn.close()
        if row:
            contact_info, display_name = row
            return {
                "full_name": display_name or contact_info,
                "first_name": None,
                "last_name": None,
            }
    except Exception:
        return None
    return None


def _lookup_prepared_contact(prepared_db: str, handle: str) -> Optional[str]:
    """Lookup display name in prepared contacts table using normalized variants."""
    variants = normalize_handle_variants(handle)
    if not variants:
        return None
    try:
        conn = sqlite3.connect(prepared_db)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(variants))
        cur.execute(
            f"SELECT display_name FROM contacts WHERE contact_info IN ({placeholders}) LIMIT 1",
            variants,
        )
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except Exception:
        return None
    return None


def _resolve_handle_display(prepared_db: Optional[str], handle: Optional[str]) -> Optional[str]:
    """Resolve a handle to display name using prepared contacts then AddressBook with variants."""
    if not handle:
        return None
    variants = normalize_handle_variants(handle)
    if prepared_db:
        name = _lookup_prepared_contact(prepared_db, handle)
        if name:
            return name
        # If not found on raw, try other variants explicitly
        if len(variants) > 1:
            try:
                conn = sqlite3.connect(prepared_db)
                cur = conn.cursor()
                placeholders = ",".join("?" * len(variants))
                cur.execute(
                    f"SELECT display_name FROM contacts WHERE contact_info IN ({placeholders}) LIMIT 1",
                    variants,
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    return row[0]
            except Exception:
                pass
    # AddressBook fallback with variants
    for v in variants:
        try:
            info = get_contact_info_by_handle(v)
            if info and info.get("full_name"):
                return info["full_name"]
        except Exception:
            continue
    return None


def _build_participant_name_map(source_db: str, prepared_db: Optional[str], chat_ids: List[int]) -> Dict[str, str]:
    """Resolve participant handles to names using prepared contacts then AddressBook."""
    if not chat_ids:
        return {}
    mapping: Dict[str, str] = {}
    placeholders = ",".join(["?"] * len(chat_ids))
    try:
        conn = sqlite3.connect(source_db)
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT DISTINCT h.id
            FROM chat_handle_join chj
            JOIN handle h ON chj.handle_id = h.ROWID
            WHERE chj.chat_id IN ({placeholders})
            """,
            chat_ids,
        )
        handles = [r[0] for r in cur.fetchall() if r and r[0]]
        conn.close()
    except Exception:
        handles = []

    for raw_handle in handles:
        display = _resolve_handle_display(prepared_db, raw_handle)
        if display:
            for v in normalize_handle_variants(raw_handle):
                mapping[v] = display
    return mapping


def _find_equivalent_chat_ids(chat_id: int, source_db_path: str) -> Optional[List[int]]:
    """
    Find other chat_ids with identical participant sets (using source chat.db).
    Returns None on error to fall back to the single chat_id.
    """
    try:
        conn = sqlite3.connect(source_db_path)
        try:
            cur = conn.cursor()
            # Get participant handles for the target chat
            cur.execute(
                """
                SELECT h.id
                FROM chat_handle_join chj
                JOIN handle h ON chj.handle_id = h.ROWID
                WHERE chj.chat_id = ?
                """,
                (chat_id,),
            )
            handles = [normalize_handle(r[0]) for r in cur.fetchall() if r and r[0]]
            handles = [h for h in handles if h]
            if not handles:
                return None
            handle_set = set(handles)

            # Find other chats with exactly this participant set
            placeholders = ",".join("?" * len(handle_set))
            # Chats whose participant count matches and whose handles set matches
            cur.execute(
                f"""
                WITH ch_participants AS (
                    SELECT chj.chat_id, GROUP_CONCAT(DISTINCT h.id) AS handles_raw
                    FROM chat_handle_join chj
                    JOIN handle h ON chj.handle_id = h.ROWID
                    GROUP BY chj.chat_id
                )
                SELECT chat_id
                FROM ch_participants
                WHERE chat_id IN (
                    SELECT chat_id FROM chat_handle_join GROUP BY chat_id HAVING COUNT(DISTINCT handle_id)=?
                )
                """,
                (len(handle_set),),
            )
            candidate_ids = [int(r[0]) for r in cur.fetchall()]
            if not candidate_ids:
                return [chat_id]

            # Fetch handles for candidates and match sets
            matches: List[int] = []
            for cid in candidate_ids:
                cur.execute(
                    """
                    SELECT h.id
                    FROM chat_handle_join chj
                    JOIN handle h ON chj.handle_id = h.ROWID
                    WHERE chj.chat_id = ?
                    """,
                    (cid,),
                )
                ch_handles = [normalize_handle(r[0]) for r in cur.fetchall() if r and r[0]]
                ch_handles = [h for h in ch_handles if h]
                if set(ch_handles) == handle_set:
                    matches.append(cid)

            return matches or [chat_id]
        finally:
            conn.close()
    except Exception:
        return None


async def _refresh_token_if_needed(db: Session, token_entry: SpotifyToken) -> SpotifyToken:
    """Refresh Spotify token if expired."""
    if not token_entry.expires_at:
        return token_entry

    # Check if token is expired
    now = datetime.now(timezone.utc)
    expires_at = token_entry.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now >= expires_at:
        logger.info("Spotify token expired, refreshing...")
        if not token_entry.refresh_token:
            raise HTTPException(status_code=401, detail="Token expired and no refresh token available")

        token_url = "https://accounts.spotify.com/api/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token_entry.refresh_token,
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "client_secret": settings.SPOTIFY_CLIENT_SECRET,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(token_url, data=payload)
                response.raise_for_status()
                tokens = response.json()
                token_entry.access_token = tokens["access_token"]
                if tokens.get("refresh_token"):
                    token_entry.refresh_token = tokens["refresh_token"]
                if tokens.get("expires_in"):
                    token_entry.expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
                token_entry.updated_at = datetime.now(timezone.utc)
                db.commit()
                logger.info("Token refreshed successfully")
            except httpx.HTTPStatusError:
                logger.error("Failed to refresh token: HTTP error")
                raise HTTPException(status_code=401, detail="Failed to refresh token")
            except httpx.TimeoutException:
                logger.error("Token refresh request timed out")
                raise HTTPException(status_code=504, detail="Token refresh request timed out")
            except httpx.RequestError as e:
                logger.error(f"Token refresh request error: {e}")
                raise HTTPException(status_code=502, detail=f"Failed to refresh token: {str(e)}")

    return token_entry


async def _periodic_prepared_refresh(interval_seconds: int = 300):
    """Background refresher that keeps prepared DB in sync and tracks staleness."""
    global PREPARED_STATUS
    while True:
        try:
            db_path = get_db_path()
            if not db_path or not os.path.exists(db_path):
                PREPARED_STATUS = {
                    "last_prepared_date": None,
                    "source_max_date": None,
                    "staleness_seconds": None,
                    "last_check_ts": time.time(),
                }
            else:
                loop = asyncio.get_event_loop()
                source_max_date = await loop.run_in_executor(None, get_source_max_date, db_path)

                prepared_path = PREPARED_DB_PATH
                prepared_date = None
                if prepared_path and os.path.exists(prepared_path):
                    prepared_date = get_last_processed_date(Path(prepared_path))

                needs_refresh = False
                if source_max_date and prepared_date:
                    needs_refresh = source_max_date > prepared_date
                elif source_max_date and not prepared_date:
                    needs_refresh = True

                if needs_refresh:
                    await loop.run_in_executor(None, _refresh_prepared_db, db_path)
                    prepared_path = PREPARED_DB_PATH
                    if prepared_path and os.path.exists(prepared_path):
                        prepared_date = get_last_processed_date(Path(prepared_path))

                staleness = _compute_staleness_seconds(source_max_date, prepared_date)
                PREPARED_STATUS = {
                    "last_prepared_date": prepared_date,
                    "source_max_date": source_max_date,
                    "staleness_seconds": staleness,
                    "last_check_ts": time.time(),
                }
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"Prepared DB refresh loop error: {exc}", exc_info=True)
        await asyncio.sleep(interval_seconds)
