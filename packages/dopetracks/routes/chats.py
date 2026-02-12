"""
Chat search, listing, messages, and contact photo endpoints.
"""
import os
import logging
import asyncio
import json
import queue
import time
import sqlite3
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..utils.helpers import get_db_path
from ..utils import dictionaries
from ..processing.imessage_data_processing.prepared_messages import (
    chat_search_prepared,
)
from ..processing.contacts_data_processing.import_contact_info import (
    get_contact_info_by_handle,
)
from ..processing.imessage_data_processing.handle_utils import (
    normalize_handle_variants,
)
from ..processing.imessage_data_processing.optimized_queries import (
    advanced_chat_search,
    advanced_chat_search_streaming,
)
from .helpers import (
    _refresh_prepared_db,
    _resolve_sender_name_from_prepared,
    _build_participant_name_map,
    _find_equivalent_chat_ids,
    _chat_cache,
    CHAT_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chats"])


@router.get("/chats")
async def get_all_chats(db: Session = Depends(get_db)):
    """Get all chats with basic statistics."""
    try:
        from ..processing.imessage_data_processing.optimized_queries import get_chat_list
        start_time = time.perf_counter()

        db_path = get_db_path()
        if not db_path:
            logger.error("get_all_chats: get_db_path() returned None - check logs for details")
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please grant Full Disk Access in System Preferences > Security & Privacy > Privacy > Full Disk Access, or upload your Messages database file manually."
            )

        if not os.path.exists(db_path):
            logger.error(f"get_all_chats: Database path does not exist: {db_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )

        # Refresh prepared DB incrementally
        prepared_db = _refresh_prepared_db(db_path)

        now = time.monotonic()
        cache_key = f"{db_path}|{prepared_db or ''}"
        cache_entry = _chat_cache.get(cache_key)
        if cache_entry:
            ts, cached = cache_entry
            if now - ts < CHAT_CACHE_TTL_SECONDS:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.info(f"get_all_chats: Served {len(cached)} chats from cache in {elapsed_ms:.0f} ms (TTL {CHAT_CACHE_TTL_SECONDS}s)")
                return cached

        logger.info(f"get_all_chats: Loading all chats from database {db_path}")
        results = get_chat_list(db_path, prepared_db_path=prepared_db)
        _chat_cache[cache_key] = (now, results)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"get_all_chats: Found {len(results)} chats in {elapsed_ms:.0f} ms (cached for {CHAT_CACHE_TTL_SECONDS}s)")
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting all chats: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error loading chats: {str(e)}"
        )


@router.get("/chat-search-optimized")
async def chat_search_optimized(
    query: str,
    db: Session = Depends(get_db)
):
    """Optimized chat search using direct SQL queries."""
    try:
        from ..processing.imessage_data_processing.optimized_queries import search_chats_by_name

        db_path = get_db_path()
        if not db_path:
            logger.error("chat_search_optimized: get_db_path() returned None - check logs for details")
            raise HTTPException(
                status_code=400,
                detail="No Messages database found. Please grant Full Disk Access in System Preferences > Security & Privacy > Privacy > Full Disk Access, or upload your Messages database file manually."
            )

        if not os.path.exists(db_path):
            logger.error(f"chat_search_optimized: Database path does not exist: {db_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Messages database not found at {db_path}"
            )

        logger.info(f"chat_search_optimized: Searching chats with query '{query}' in database {db_path}")
        results = search_chats_by_name(db_path, query)
        logger.info(f"chat_search_optimized: Found {len(results)} results")
        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )


@router.get("/chat-search-prepared")
async def chat_search_prepared_endpoint(
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[str] = None,  # currently unused in prepared search
    message_content: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")
        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db:
            raise HTTPException(status_code=500, detail="Failed to prepare messages database")

        participant_list = None
        if participant_names:
            participant_list = [name.strip() for name in participant_names.split(',') if name.strip()]

        results = chat_search_prepared(
            prepared_db,
            query,
            start_date,
            end_date,
            participant_list,
            message_content,
            limit_to_recent=5000
        )
        logger.info(f"chat_search_prepared: Found {len(results)} results")
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat_search_prepared: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-search-advanced")
async def chat_search_advanced(
    query: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    participant_names: Optional[str] = None,  # Comma-separated list
    message_content: Optional[str] = None,
    stream: bool = False,  # Enable streaming mode
    db: Session = Depends(get_db)
):
    """Advanced chat search with multiple filter criteria. Supports streaming results."""
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")

        # Keep prepared DB up-to-date and reuse it for message-content filtering
        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db or not os.path.exists(prepared_db):
            logger.error("chat_search_advanced: prepared DB not found")
            raise HTTPException(
                status_code=500,
                detail="Prepared messages database not found. Please retry startup."
            )

        # Parse participant names (comma-separated)
        participant_list = None
        if participant_names:
            participant_list = [name.strip() for name in participant_names.split(',') if name.strip()]

        logger.info(f"chat_search_advanced: Searching with query='{query}', start_date='{start_date}', end_date='{end_date}', participants={participant_list}, message_content='{message_content}', stream={stream}")

        if stream:
            # Streaming mode: yield results as they're found
            async def generate_results():
                loop = asyncio.get_event_loop()
                try:
                    # Create a queue to pass results from thread to async generator
                    result_queue = queue.Queue()
                    exception_queue = queue.Queue()

                    def run_search():
                        try:
                            result_count = 0
                            for result in advanced_chat_search_streaming(
                                db_path=source_db,
                                query=query,
                                start_date=start_date,
                                end_date=end_date,
                                participant_names=participant_list,
                                message_content=message_content,
                                limit_to_recent=None,
                                prepared_db_path=prepared_db,
                            ):
                                result_count += 1
                                result_queue.put(result)
                            logger.info(f"Streaming search completed: {result_count} results found")
                            result_queue.put(None)  # Sentinel to signal completion
                        except Exception as e:
                            logger.error(f"Error in run_search: {e}", exc_info=True)
                            exception_queue.put(e)
                            # Also put sentinel to signal completion even on error
                            try:
                                result_queue.put(None)
                            except:
                                pass

                    # Start search in thread pool with timeout
                    search_task = loop.run_in_executor(None, run_search)

                    # Yield results as they arrive (with overall timeout)
                    timeout_seconds = 300  # 5 minutes max for streaming search
                    start_time = time.time()

                    while True:
                        # Check for timeout
                        elapsed = time.time() - start_time
                        if elapsed > timeout_seconds:
                            logger.warning(f"Streaming search timed out after {timeout_seconds} seconds")
                            search_task.cancel()
                            yield f"data: {json.dumps({'status': 'error', 'message': f'Search timed out after {timeout_seconds} seconds'})}\n\n"
                            break
                        # Check for exceptions
                        try:
                            exc = exception_queue.get_nowait()
                            raise exc
                        except queue.Empty:
                            pass

                        # Check for results
                        try:
                            result = result_queue.get(timeout=0.1)
                            if result is None:  # Completion sentinel
                                break
                            yield f"data: {json.dumps(result)}\n\n"
                            await asyncio.sleep(0)  # Yield to event loop
                        except queue.Empty:
                            # Check if search task is done
                            if search_task.done():
                                # Process any remaining results
                                while True:
                                    try:
                                        result = result_queue.get_nowait()
                                        if result is None:
                                            break
                                        yield f"data: {json.dumps(result)}\n\n"
                                        await asyncio.sleep(0)
                                    except queue.Empty:
                                        break
                                break
                            await asyncio.sleep(0.01)  # Small delay before checking again

                    yield f"data: {json.dumps({'status': 'complete'})}\n\n"
                except Exception as e:
                    logger.error(f"Error in streaming search: {e}", exc_info=True)
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"

            return StreamingResponse(
                generate_results(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            # Non-streaming mode: return all results at once
            loop = asyncio.get_event_loop()
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: list(
                            advanced_chat_search(
                                db_path=source_db,
                                query=query,
                                start_date=start_date,
                                end_date=end_date,
                                participant_names=participant_list,
                                message_content=message_content,
                                limit_to_recent=None,
                                prepared_db_path=prepared_db,
                            )
                        ),
                    ),
                    timeout=120.0
                )
                logger.info(f"chat_search_advanced: Found {len(results)} results")
                return results
            except asyncio.TimeoutError:
                logger.error("chat_search_advanced: Search operation timed out after 120 seconds")
                raise HTTPException(
                    status_code=504,
                    detail="Search operation timed out. Try narrowing your search criteria (date range, participants, or message content)."
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat search: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error searching chats: {str(e)}"
        )


@router.get("/chat/{chat_id}/recent-messages")
async def get_recent_messages(
    chat_id: int,
    chat_ids: Optional[str] = None,
    canonical_chat_id: Optional[str] = None,
    limit: int = 5,
    offset: int = 0,
    order: str = "desc",
    search: Optional[str] = None,
):
    """Get recent messages for a chat."""
    try:
        source_db = get_db_path()
        if not source_db or not os.path.exists(source_db):
            raise HTTPException(status_code=400, detail="No Messages database found")

        prepared_db = _refresh_prepared_db(source_db)
        if not prepared_db:
            raise HTTPException(status_code=500, detail="Failed to prepare messages database")

        chat_id_list: List[int] = [chat_id]
        participant_name_map: Dict[str, str] = {}
        if canonical_chat_id:
            # Resolve chat_ids from prepared DB mapping
            try:
                conn_map = sqlite3.connect(prepared_db)
                cur_map = conn_map.cursor()
                cur_map.execute(
                    "SELECT chat_ids FROM chat_groups WHERE canonical_chat_id = ?",
                    (canonical_chat_id,),
                )
                row = cur_map.fetchone()
                if row and row[0]:
                    chat_id_list = [int(x) for x in row[0].split(",") if x.strip()]
                cur_map.close()
                conn_map.close()
            except Exception:
                pass
        elif chat_ids:
            try:
                parsed_ids = [int(x) for x in chat_ids.split(",") if x.strip()]
                if parsed_ids:
                    chat_id_list = parsed_ids
            except Exception:
                pass
        else:
            # If client did not pass group ids, try to find equivalent chats by participants
            equivalents = _find_equivalent_chat_ids(chat_id, source_db)
            if equivalents:
                chat_id_list = equivalents

        # Build participant name map for better sender resolution
        participant_name_map = _build_participant_name_map(source_db, prepared_db, chat_id_list)

        placeholders = ",".join(["?"] * len(chat_id_list))
        conn = sqlite3.connect(prepared_db)
        try:
            cur = conn.cursor()
            order_dir = "DESC" if order.lower() != "asc" else "ASC"
            params: List[Any] = chat_id_list + [limit, offset]
            search_clause = ""
            if search:
                search_clause = "AND m.rowid IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)"
                params = chat_id_list + [search, limit, offset]
            query = f"""
                SELECT
                    m.message_id,
                    m.text,
                    m.date,
                    m.sender_handle,
                    m.is_from_me,
                    m.has_spotify_link,
                    m.spotify_url,
                    m.associated_message_type,
                    m.associated_message_guid,
                    m.message_guid
                FROM messages m
                WHERE m.chat_id IN ({placeholders})
                {search_clause}
                ORDER BY m.date {order_dir}
                LIMIT ?
                OFFSET ?
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            messages_raw = []
            for row in rows:
                (
                    message_id,
                    text,
                    date_val,
                    sender_handle,
                    is_from_me,
                    has_spotify,
                    spotify_url,
                    associated_message_type,
                    associated_message_guid,
                    message_guid,
                ) = row
                messages_raw.append(
                    {
                        "id": str(message_id),
                        "text": text or "",
                        "date": date_val,
                        "sender_handle": sender_handle,
                        "is_from_me": bool(is_from_me),
                        "has_spotify_link": bool(has_spotify),
                        "spotify_url": spotify_url,
                        "associated_message_type": associated_message_type,
                        "associated_message_guid": associated_message_guid,
                        "message_guid": message_guid,
                    }
                )

            # Split base messages and reactions
            base_messages: Dict[str, Dict[str, Any]] = {}
            reactions_by_target: Dict[str, List[Dict[str, Any]]] = {}

            for msg in messages_raw:
                assoc_type = msg.get("associated_message_type")
                is_reaction = assoc_type not in (None, 0)
                sender_handle = msg.get("sender_handle")

                # Resolve sender name
                sender_name = sender_handle or "Unknown"
                if msg.get("is_from_me"):
                    sender_name = "You"
                else:
                    # Try participant map first
                    for v in normalize_handle_variants(sender_handle):
                        if v in participant_name_map:
                            sender_name = participant_name_map[v]
                            break
                    # First try prepared DB contacts
                    if sender_name == sender_handle or sender_name == "Unknown":
                        resolved = _resolve_sender_name_from_prepared(prepared_db, sender_handle)
                        if resolved and resolved.get("full_name"):
                            sender_name = resolved["full_name"]
                        elif sender_name == "Unknown" or sender_name == sender_handle:
                            try:
                                info = get_contact_info_by_handle(sender_handle)
                                if info and info.get("full_name"):
                                    sender_name = info["full_name"]
                            except Exception:
                                pass

                if is_reaction:
                    reaction_type = dictionaries.reaction_dict.get(assoc_type, "reaction")
                    target_guid = msg.get("associated_message_guid")
                    if not target_guid:
                        continue
                    reactions_by_target.setdefault(target_guid, []).append(
                        {
                            "type": reaction_type,
                            "sender": sender_name,
                            "is_from_me": msg.get("is_from_me", False),
                            "date": msg.get("date"),
                            "message_id": msg.get("id"),
                        }
                    )
                else:
                    key = msg.get("message_guid") or msg["id"]
                    base_messages[key] = {
                        "id": msg["id"],
                        "text": msg["text"],
                        "date": msg["date"],
                        "sender": sender_handle,
                        "sender_name": sender_name,
                        "sender_full_name": sender_name,
                        "is_from_me": msg["is_from_me"],
                        "has_spotify_link": msg["has_spotify_link"],
                        "spotify_url": msg["spotify_url"],
                        "reactions": [],
                        "message_guid": msg.get("message_guid"),
                    }

            # Attach reactions to targets
            for target_guid, reacts in reactions_by_target.items():
                target = base_messages.get(target_guid)
                if target:
                    target["reactions"].extend(reacts)

            # Keep ordering of non-reaction messages
            ordered = [
                m for m in messages_raw
                if m.get("associated_message_type") in (None, 0)
            ]
            result_messages = []
            for m in ordered:
                key = m.get("message_guid") or m["id"]
                if key in base_messages:
                    out = base_messages[key].copy()
                    out.pop("message_guid", None)
                    result_messages.append(out)

            return {"messages": result_messages}
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contact-photo/{unique_id}")
async def get_contact_photo(unique_id: str):
    """Get contact photo by unique ID."""
    try:
        import sqlite3
        from pathlib import Path
        from urllib.parse import unquote

        # Decode URL-encoded unique_id
        unique_id = unquote(unique_id)
        logger.info(f"Looking for contact photo with unique_id: {unique_id}")

        # Find AddressBook database
        sources_dir = Path.home() / "Library/Application Support/AddressBook/Sources"
        if not sources_dir.exists():
            raise HTTPException(status_code=404, detail="AddressBook not found")

        # Collect all source directories with databases
        all_source_paths = []
        for folder in sources_dir.iterdir():
            potential_db = folder / "AddressBook-v22.abcddb"
            if potential_db.exists():
                all_source_paths.append(folder)

        if not all_source_paths:
            raise HTTPException(status_code=404, detail="AddressBook database not found")

        # Helper function to check for external file from UUID reference
        def check_external_file(data_blob, source_path, all_source_paths=None):
            """Check if data_blob is a UUID reference and look for external file."""
            if not data_blob or len(data_blob) >= 100:
                return None
            try:
                # Strip leading non-printable bytes (like \x00, \x01, \x02, etc.)
                # Try to decode, but handle binary data that might have leading bytes
                uuid_ref = data_blob.decode('utf-8', errors='ignore')
                # Strip common leading bytes and whitespace
                uuid_ref = uuid_ref.lstrip('\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f')
                uuid_ref = uuid_ref.strip('\x00').strip()
                logger.debug(f"Decoded UUID reference: {uuid_ref!r} (length: {len(uuid_ref)}, original blob length: {len(data_blob)})")
                # Check if it looks like a UUID (has dashes and is reasonable length)
                if '-' in uuid_ref and len(uuid_ref) > 30:
                    # First try the current source directory
                    search_paths = [source_path]
                    # If provided, also search other source directories
                    if all_source_paths:
                        search_paths.extend([sp for sp in all_source_paths if sp != source_path])

                    logger.debug(f"Searching for external file in {len(search_paths)} directories")
                    for search_path in search_paths:
                        external_data_dir = search_path / ".AddressBook-v22_SUPPORT" / "_EXTERNAL_DATA"
                        external_file = external_data_dir / uuid_ref
                        logger.debug(f"Checking: {external_file} (exists: {external_file.exists()})")
                        if external_file.exists():
                            # Read the external file
                            external_image = external_file.read_bytes()
                            if len(external_image) > 100:
                                logger.info(f"Found shared photo in external data: {external_file} (UUID: {uuid_ref}, size: {len(external_image)} bytes)")
                                return external_image
                            else:
                                logger.debug(f"External file too small at: {external_file} ({len(external_image)} bytes)")
                        else:
                            logger.debug(f"External file not found at: {external_file}")
                else:
                    logger.debug(f"Data doesn't look like a UUID reference (length: {len(uuid_ref)}, has dashes: {'-' in uuid_ref})")
            except Exception as e:
                logger.debug(f"Could not parse as UUID reference: {e}", exc_info=True)
            return None

        # Helper function to process and return image data
        def process_and_return_image(image_data, unique_id):
            """Process image data and return HTTP response."""
            if not image_data or len(image_data) < 100:
                return None

            # Some images may have extra bytes at the start (like \x01)
            # Check for leading non-image bytes
            if image_data[:1] == b'\x01' and image_data[1:4] in [b'\x89PN', b'\xff\xd8\xff']:
                image_data = image_data[1:]

            # Detect format
            if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                media_type = 'image/png'
            elif image_data[:4] == b'\x89PNG':
                media_type = 'image/png'
            elif image_data[:3] == b'\xff\xd8\xff':
                media_type = 'image/jpeg'
            elif image_data[:4] == b'II*\x00' or image_data[:4] == b'MM\x00*':
                media_type = 'image/tiff'
            else:
                # Unknown format, try to detect from first few bytes
                logger.warning(f"Unknown image format for unique_id: {unique_id}, first bytes: {image_data[:10].hex()}")
                media_type = 'image/jpeg'

            logger.info(f"Found contact photo for unique_id: {unique_id}, size: {len(image_data)} bytes, type: {media_type}")
            return Response(content=image_data, media_type=media_type)

        # Search through all source directories
        for source_path in all_source_paths:
            db_path = source_path / "AddressBook-v22.abcddb"

            # Query for photo
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Try with and without :ABPerson suffix
            for uid_variant in [unique_id, unique_id.replace(':ABPerson', ''), unique_id + ':ABPerson']:
                cursor.execute("""
                    SELECT ZIMAGEDATA, ZTHUMBNAILIMAGEDATA
                    FROM ZABCDRECORD
                    WHERE ZUNIQUEID = ?
                """, (uid_variant,))

                row = cursor.fetchone()
                if row:
                    logger.debug(f"Found row in database {db_path} for unique_id variant: {uid_variant}")
                    image_data = row[0]
                    thumbnail_data = row[1]

                    logger.debug(f"Image data: {len(image_data) if image_data else 0} bytes, Thumbnail: {len(thumbnail_data) if thumbnail_data else 0} bytes")

                    # Check ZIMAGEDATA (full image)
                    if image_data:
                        if len(image_data) > 100:
                            # Actual image data
                            logger.debug(f"Found full image data ({len(image_data)} bytes)")
                            result = process_and_return_image(image_data, unique_id)
                            if result:
                                conn.close()
                                return result
                        else:
                            # Might be a UUID reference - check external file
                            logger.debug(f"Image data is small ({len(image_data)} bytes), checking for UUID reference")
                            external_image = check_external_file(image_data, source_path, all_source_paths)
                            if external_image:
                                logger.info(f"Found external image file for unique_id: {unique_id}")
                                result = process_and_return_image(external_image, unique_id)
                                if result:
                                    conn.close()
                                    return result
                            else:
                                logger.debug(f"No external file found for small image data")
                    else:
                        logger.debug(f"No image data in ZIMAGEDATA column")

                    # If no full image, check thumbnail
                    if thumbnail_data:
                        if len(thumbnail_data) > 100:
                            # Actual image data
                            logger.debug(f"Found thumbnail image data ({len(thumbnail_data)} bytes)")
                            result = process_and_return_image(thumbnail_data, unique_id)
                            if result:
                                conn.close()
                                return result
                        else:
                            # Might be a UUID reference - check external file
                            logger.debug(f"Thumbnail data is small ({len(thumbnail_data)} bytes), checking for UUID reference")
                            external_image = check_external_file(thumbnail_data, source_path, all_source_paths)
                            if external_image:
                                logger.info(f"Found external thumbnail file for unique_id: {unique_id}")
                                result = process_and_return_image(external_image, unique_id)
                                if result:
                                    conn.close()
                                    return result
                            else:
                                logger.debug(f"No external file found for small thumbnail data")
                    else:
                        logger.debug(f"No thumbnail data in ZTHUMBNAILIMAGEDATA column")
                else:
                    logger.debug(f"No row found in database {db_path} for unique_id variant: {uid_variant}")

            conn.close()

        # Return 404 if photo not found
        logger.warning(f"Contact photo not found for unique_id: {unique_id}")
        raise HTTPException(status_code=404, detail=f"Photo not found for unique_id: {unique_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
