"""
Playlist creation endpoints.
"""
import logging
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import SpotifyToken
from ..utils.helpers import get_db_path
from .helpers import _refresh_token_if_needed

logger = logging.getLogger(__name__)

router = APIRouter(tags=["playlists"])


@router.post("/create-playlist-optimized-stream")
async def create_playlist_optimized_stream(
    request: Request,
    playlist_name: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    selected_chat_ids: Optional[str] = Form(None),
    existing_playlist_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Create playlist using optimized direct SQL queries with streaming progress."""
    # Support JSON payloads (the macOS app posts JSON) and fall back to form data
    if not all([playlist_name, start_date, end_date, selected_chat_ids]):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            playlist_name = playlist_name or payload.get("playlist_name") or payload.get("playlistName")
            start_date = start_date or payload.get("start_date") or payload.get("startDate")
            end_date = end_date or payload.get("end_date") or payload.get("endDate")
            existing_playlist_id = existing_playlist_id or payload.get("existing_playlist_id") or payload.get("playlist_id")
            if not selected_chat_ids:
                chat_ids_value = payload.get("selected_chat_ids") or payload.get("chat_ids")
                if isinstance(chat_ids_value, list):
                    try:
                        selected_chat_ids = json.dumps(chat_ids_value)
                    except Exception:
                        pass
                elif isinstance(chat_ids_value, str):
                    selected_chat_ids = chat_ids_value

    # Provide safe defaults when optional inputs are missing/blank
    now_iso = datetime.now(timezone.utc).isoformat()
    start_date = start_date or "2000-01-01T00:00:00+00:00"
    end_date = end_date or now_iso
    selected_chat_ids = selected_chat_ids or "[]"
    playlist_name = playlist_name or "Dopetracks Playlist"

    async def generate_progress():
        try:
            # Validate date strings early to avoid crashing during conversion
            try:
                datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            except Exception:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid date format'})}\n\n"
                await asyncio.sleep(0)
                return
            from ..processing.imessage_data_processing.optimized_queries import (
                query_messages_with_urls
            )
            from ..processing.imessage_data_processing import parsing_utils as pu
            from ..processing.spotify_interaction import spotify_db_manager as sdm
            from ..processing.spotify_interaction import create_spotify_playlist as csp
            from ..processing.contacts_data_processing.import_contact_info import get_contact_info_by_handle
            import spotipy
            import pandas as pd

            # Parse selected chat IDs
            try:
                chat_ids = json.loads(selected_chat_ids) if selected_chat_ids else []
                chat_ids = [int(cid) for cid in chat_ids]
            except (json.JSONDecodeError, ValueError, TypeError):
                yield f"data: {json.dumps({'status': 'error', 'message': 'Invalid chat selection format'})}\n\n"
                await asyncio.sleep(0)
                return

            if not chat_ids:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Please select at least one chat'})}\n\n"
                await asyncio.sleep(0)
                return

            # Get database path
            db_path = get_db_path()
            if not db_path:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No Messages database found'})}\n\n"
                await asyncio.sleep(0)
                return

            yield f"data: {json.dumps({'status': 'progress', 'stage': 'querying', 'message': f'Querying messages from {len(chat_ids)} chats...', 'progress': 10})}\n\n"
            await asyncio.sleep(0)

            # Query messages
            messages_df = query_messages_with_urls(db_path, chat_ids, start_date, end_date)

            if messages_df.empty:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No messages found', 'tracks_added': 0, 'track_details': []})}\n\n"
                await asyncio.sleep(0)
                return

            yield f"data: {json.dumps({'status': 'progress', 'stage': 'extracting', 'message': f'Found {len(messages_df)} messages. Extracting URLs...', 'progress': 20})}\n\n"
            await asyncio.sleep(0)

            # Extract URLs
            text_column = 'final_text' if 'final_text' in messages_df.columns else 'text'
            url_to_message = {}
            skipped_urls = []
            other_links = []

            for idx, row in messages_df.iterrows():
                text = row.get(text_column)
                if pd.notna(text) and text:
                    spotify_urls = pu.extract_spotify_urls(str(text))
                    all_urls = pu.extract_all_urls(str(text))

                    # Determine sender and enrich with contact info
                    if bool(row.get('is_from_me', False)):
                        sender_name = "You"
                        sender_full_name = "You"
                        sender_first_name = None
                        sender_last_name = None
                        sender_unique_id = None
                    else:
                        # Get sender contact (phone/email from handle.id, not ROWID)
                        sender_contact = row.get('sender_contact')
                        contact_info = {}

                        # Try to get contact info by sender_contact (phone/email)
                        if pd.notna(sender_contact) and sender_contact:
                            try:
                                contact_info = get_contact_info_by_handle(str(sender_contact)) or {}
                            except Exception as e:
                                logger.debug(f"Error getting contact info for {sender_contact}: {e}")
                                pass

                        # Use contact full name if available, otherwise fall back to phone/email or chat name
                        if contact_info.get("full_name"):
                            sender_name = contact_info["full_name"]
                            sender_full_name = contact_info["full_name"]
                            sender_first_name = contact_info.get("first_name")
                            sender_last_name = contact_info.get("last_name")
                            sender_unique_id = contact_info.get("unique_id")
                        elif pd.notna(sender_contact) and sender_contact:
                            sender_name = str(sender_contact)
                            sender_full_name = str(sender_contact)
                            sender_first_name = None
                            sender_last_name = None
                            sender_unique_id = None
                        else:
                            sender_name = row.get('chat_name', 'Unknown Sender')
                            sender_full_name = sender_name
                            sender_first_name = None
                            sender_last_name = None
                            sender_unique_id = None

                    message_info = {
                        "message_text": str(text),
                        "sender_name": sender_name,
                        "sender_full_name": sender_full_name,
                        "sender_first_name": sender_first_name,
                        "sender_last_name": sender_last_name,
                        "sender_unique_id": sender_unique_id,
                        "is_from_me": bool(row.get('is_from_me', False)),
                        "date": row.get('date_utc', ''),
                        "chat_name": row.get('chat_name', '')
                    }

                    # Process Spotify URLs
                    for url in spotify_urls:
                        _, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                        if '/track/' in url or entity_type == 'track':
                            if url not in url_to_message:
                                url_to_message[url] = {**message_info, "entity_type": entity_type or "track"}
                        else:
                            skipped_info = {
                                "url": url,
                                "entity_type": entity_type or "unknown",
                                "spotify_id": spotify_id,
                                **message_info
                            }
                            skipped_urls.append(skipped_info)

                    # Track non-Spotify links
                    spotify_url_set = set(spotify_urls)
                    for url_info in all_urls:
                        url = url_info["url"]
                        url_type = url_info["type"]
                        if url_type != "spotify" and url not in spotify_url_set:
                            other_link_info = {
                                "url": url,
                                "link_type": url_type,
                                **message_info
                            }
                            other_links.append(other_link_info)

            track_urls = list(url_to_message.keys())

            if not track_urls:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No Spotify track links found', 'tracks_added': 0, 'total_tracks_found': 0, 'track_details': [], 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                await asyncio.sleep(0)
                return

            yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Found {len(track_urls)} track URLs. Processing tracks...', 'progress': 30})}\n\n"
            await asyncio.sleep(0)

            # Get Spotify tokens
            token_entry = db.query(SpotifyToken).first()
            if not token_entry:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Spotify not authorized'})}\n\n"
                await asyncio.sleep(0)
                return

            # Refresh token if needed
            token_entry = await _refresh_token_if_needed(db, token_entry)

            sp = spotipy.Spotify(auth=token_entry.access_token)
            user_id = csp.get_user_id(sp)

            # Get or create playlist
            if existing_playlist_id:
                try:
                    playlist = sp.playlist(existing_playlist_id)
                    logger.info(f"Using existing playlist: {playlist['name']}")
                except:
                    playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)
            else:
                playlist = csp.find_or_create_playlist(sp, user_id, playlist_name, public=True)

            # Get existing tracks
            existing_tracks = csp.get_all_playlist_items(sp, playlist['id'])
            existing_track_ids = set(csp.get_song_ids_from_spotify_items(existing_tracks))

            # Process tracks
            track_details = []
            track_ids = []
            processed_tracks = 0

            for url in track_urls:
                message_info = url_to_message.get(url, {})
                track_info = {
                    "url": url,
                    "track_id": None,
                    "status": "pending",
                    "error": None,
                    "track_name": None,
                    "artist": None,
                    "spotify_url": None,
                    "message_text": message_info.get("message_text", ""),
                    "sender_name": message_info.get("sender_name", "Unknown"),
                    "sender_full_name": message_info.get("sender_full_name"),
                    "sender_first_name": message_info.get("sender_first_name"),
                    "sender_last_name": message_info.get("sender_last_name"),
                    "sender_unique_id": message_info.get("sender_unique_id"),
                    "is_from_me": message_info.get("is_from_me", False),
                    "message_date": message_info.get("date", ""),
                    "chat_name": message_info.get("chat_name", "")
                }

                try:
                    _, spotify_id, entity_type = sdm.normalize_and_extract_id(url)

                    if entity_type != 'track':
                        track_info["status"] = "skipped"
                        track_info["error"] = f"Not a track (entity type: {entity_type})"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue

                    if not spotify_id:
                        track_info["status"] = "error"
                        track_info["error"] = "Could not extract Spotify ID from URL"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue

                    track_info["track_id"] = spotify_id

                    if not (spotify_id.isalnum() and 15 <= len(spotify_id) <= 22):
                        track_info["status"] = "error"
                        track_info["error"] = f"Invalid ID format"
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue

                    if spotify_id in existing_track_ids:
                        track_info["status"] = "skipped"
                        track_info["error"] = "Already in playlist"
                        try:
                            track_data = sp.track(spotify_id)
                            track_info["track_name"] = track_data.get("name", "Unknown")
                            track_info["artist"] = ", ".join([a["name"] for a in track_data.get("artists", [])])
                            track_info["spotify_url"] = track_data.get("external_urls", {}).get("spotify")
                        except:
                            pass
                        track_details.append(track_info)
                        processed_tracks += 1
                        continue

                    # Try to get track data
                    try:
                        track_data = sp.track(spotify_id)
                        track_info["track_name"] = track_data.get("name", "Unknown")
                        track_info["artist"] = ", ".join([a["name"] for a in track_data.get("artists", [])])
                        track_info["spotify_url"] = track_data.get("external_urls", {}).get("spotify")
                        track_info["status"] = "valid"
                        track_ids.append(spotify_id)
                        track_details.append(track_info)
                    except Exception as e:
                        track_info["status"] = "error"
                        error_str = str(e)
                        if "Invalid base62 id" in error_str or "invalid id" in error_str.lower():
                            track_info["error"] = f"Invalid track ID"
                        elif "401" in error_str or "expired" in error_str.lower():
                            track_info["error"] = f"Spotify token expired - please re-authorize"
                        else:
                            error_msg = error_str[:100] if len(error_str) > 100 else error_str
                            track_info["error"] = f"Spotify API error: {error_msg}"
                        track_details.append(track_info)
                        logger.warning(f"Spotify API error for track {spotify_id}: {error_str[:200]}")

                    processed_tracks += 1
                    progress = 30 + int((processed_tracks / len(track_urls)) * 50)
                    yield f"data: {json.dumps({'status': 'progress', 'stage': 'processing', 'message': f'Processed {processed_tracks}/{len(track_urls)} tracks', 'progress': progress, 'current': processed_tracks, 'total': len(track_urls)})}\n\n"
                    await asyncio.sleep(0)

                except Exception as e:
                    track_info["status"] = "error"
                    track_info["error"] = f"Processing error: {str(e)[:200]}"
                    track_details.append(track_info)
                    processed_tracks += 1

            # Add tracks to playlist
            if track_ids:
                yield f"data: {json.dumps({'status': 'progress', 'stage': 'adding', 'message': f'Adding {len(track_ids)} tracks to playlist...', 'progress': 80})}\n\n"
                await asyncio.sleep(0)

                try:
                    # Add in batches of 100 (Spotify limit)
                    for i in range(0, len(track_ids), 100):
                        batch = track_ids[i:i+100]
                        sp.playlist_add_items(playlist['id'], batch)

                    yield f"data: {json.dumps({'status': 'complete', 'message': f'Successfully added {len(track_ids)} tracks to playlist', 'tracks_added': len(track_ids), 'total_tracks_found': len(track_urls), 'playlist_id': playlist['id'], 'playlist_name': playlist['name'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'playlist': playlist, 'chat_ids': chat_ids, 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                    await asyncio.sleep(0)
                except Exception as e:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Failed to add tracks to playlist: {str(e)}', 'tracks_added': 0, 'track_details': track_details})}\n\n"
                    await asyncio.sleep(0)
            else:
                yield f"data: {json.dumps({'status': 'complete', 'message': 'No valid tracks to add', 'tracks_added': 0, 'total_tracks_found': len(track_urls), 'playlist_id': playlist['id'], 'playlist_name': playlist['name'], 'playlist_url': playlist.get('external_urls', {}).get('spotify'), 'playlist': playlist, 'chat_ids': chat_ids, 'track_details': track_details, 'skipped_urls': skipped_urls, 'other_links': other_links})}\n\n"
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Error in playlist creation stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error: {str(e)}'})}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(generate_progress(), media_type="text/event-stream")
