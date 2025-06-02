import logging
from io import StringIO
from fastapi import FastAPI, Form, Request, File, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
import asyncio
from fastapi.staticfiles import StaticFiles
import os
import time
from dotenv import load_dotenv
import requests
from typing import Optional
import json
from dopetracks.frontend_interface.core_logic import process_user_inputs
from dopetracks.utils import utility_functions as uf
from dopetracks.processing import prepare_data_main
from queue import SimpleQueue
import pandas as pd
import spotipy
from fastapi.middleware.cors import CORSMiddleware
import datetime


# Load environment variables
load_dotenv()

app = FastAPI()
port = int(os.getenv("PORT", 8888))  # Default to 8888 if PORT is not set

# Add CORS middleware so that the frontend (on port 8889) can call the backend (on port 8888) without CORS errors.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8889"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Temporary in-memory token store (use a database in production)
user_tokens = {}

# Global variable to store processed data to avoid reprocessing
_cached_data = None
_processing_status = {"is_processing": False, "progress": []}

# Set up logging configuration for the dopetracks logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("dopetracks")

# Tester
@app.get("/")
async def root():
    return {"message": "Hello, World!"}

@app.get("/get-client-id")
async def get_client_id():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    if not client_id:
        return JSONResponse(status_code=500, content={"error": "SPOTIFY_CLIENT_ID is not set"})
    return {"client_id": client_id}


@app.post("/create-playlist/")
async def create_playlist(
    playlist_name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    selected_chats: str = Form(default=""),  # JSON string of selected chat names
    existing_playlist_id: str = Form(default=None)
):
    """Create Spotify playlist from selected chats and date range using cached data"""
    try:
        logging.info(f"Playlist creation requested: '{playlist_name}' from {start_date} to {end_date}")
        
        # Check if we have cached data from search
        global _cached_data
        if _cached_data is None:
            return JSONResponse({
                "status": "error",
                "message": "No processed data available. Please search for chats first to prepare the data."
            }, status_code=400)
        
        # Parse selected chats
        chat_names = []
        if selected_chats.strip():
            try:
                chat_names = json.loads(selected_chats)
                logging.info(f"Selected chats: {chat_names}")
            except json.JSONDecodeError:
                return JSONResponse({
                    "status": "error",
                    "message": "Invalid chat selection data format."
                }, status_code=400)
        
        # Require at least one selected chat
        if not chat_names:
            return JSONResponse({
                "status": "error",
                "message": "Please select at least one chat from the search results before creating a playlist."
            }, status_code=400)
        
        # Use cached data to create playlist efficiently
        result = await create_playlist_from_cached_data(
            cached_data=_cached_data,
            playlist_name=playlist_name,
            start_date=start_date,
            end_date=end_date,
            selected_chat_names=chat_names,
            existing_playlist_id=existing_playlist_id
        )
        
        if result['status'] == 'success':
            return JSONResponse({
                "status": "success",
                "message": f"Playlist '{playlist_name}' created successfully using selected chats!",
                "tracks_processed": result.get('tracks_processed', 0),
                "playlist_name": result.get('playlist_name', playlist_name),
                "selected_chats": result.get('selected_chats', [])
            })
        else:
            return JSONResponse({
                "status": "error",
                "message": f"Error creating playlist: {'; '.join(result.get('errors', ['Unknown error']))}"
            }, status_code=400)
            
    except Exception as e:
        logging.error(f"Error in create_playlist endpoint: {str(e)}")
        return JSONResponse({
            "status": "error", 
            "message": f"Server error: {str(e)}"
        }, status_code=500)

async def create_playlist_from_cached_data(cached_data, playlist_name, start_date, end_date, selected_chat_names, existing_playlist_id=None):
    """Create playlist using already processed cached data"""
    from dopetracks.processing.spotify_interaction import spotify_db_manager as sdm
    from dopetracks.processing.spotify_interaction import create_spotify_playlist as csp
    from dopetracks.processing.imessage_data_processing import generate_summary_stats as gss
    
    def format_contributor_line(contrib_dict, label, max_contributors=3):
        if not contrib_dict:
            return f"{label}: None"
        top = sorted(contrib_dict.items(), key=lambda x: x[1], reverse=True)[:max_contributors]
        return f"{label}: " + ", ".join(f"{name} ({count})" for name, count in top)

    def format_playlist_description(date_str, num_songs, top_month, top_all):
        desc = f"Updated: {date_str} | +{num_songs} songs | "
        desc += format_contributor_line(top_month, "Top (month)") + " | "
        desc += format_contributor_line(top_all, "Top (all)") + " | Dopetracks"
        if len(desc) > 300:
            desc = desc[:297] + '...'
        return desc
    
    try:
        # Check if we have valid Spotify tokens from the web session
        access_token = user_tokens.get("access_token")
        if not access_token:
            return {
                'status': 'error',
                'errors': ['No Spotify authentication found. Please re-authenticate with Spotify.']
            }
        
        # Debug logging
        logging.debug("Selected chat names:", selected_chat_names)
        logging.debug("Date range:", start_date, "to", end_date)
        logging.debug("Total messages in cached data:", len(cached_data['messages']))

        messages_df = cached_data['messages']
        
        logging.info(f"Using cached data with {len(messages_df)} total messages")
        
        # Debug: Check what columns exist in the DataFrame
        logging.debug(f"Available columns in messages_df: {list(messages_df.columns)}")
        
        # Check if spotify_song_links column exists
        if 'spotify_song_links' not in messages_df.columns:
            logging.error("Column 'spotify_song_links' not found in messages DataFrame")
            return {
                'status': 'error',
                'errors': [f"Data structure error: 'spotify_song_links' column not found. Available columns: {list(messages_df.columns)}"]
            }
        
        # Step 1: Filter messages by date range and selected chats
        try:
            filtered_by_date = messages_df[
                (messages_df['date'] >= start_date) &
                (messages_df['date'] <= end_date) &
                (messages_df['spotify_song_links'].apply(len) > 0)
            ]
        except Exception as e:
            logging.error(f"Error filtering messages by date and spotify links: {str(e)}")
            logging.debug(f"Sample spotify_song_links values: {messages_df['spotify_song_links'].head()}")
            return {
                'status': 'error',
                'errors': [f"Error filtering messages: {str(e)}"]
            }
        logging.debug("Messages after date and spotify link filter:", len(filtered_by_date))
        if not filtered_by_date.empty:
            logging.debug("Dates of messages with Spotify links after date filter:", filtered_by_date['date'].tolist())

        # Apply chat name filter for selected chats
        filtered_messages = filtered_by_date[
            filtered_by_date['chat_name'].apply(
                lambda x: isinstance(x, str) and any(
                    (chat_name.lower() in x.lower() or x.lower() in chat_name.lower()) 
                    for chat_name in selected_chat_names
                )
            )
        ]
        logging.debug("Messages after chat name filter:", len(filtered_messages))
        if not filtered_messages.empty:
            logging.debug("Chat names in filtered messages:", filtered_messages['chat_name'].unique().tolist())
            logging.debug("Dates in filtered messages:", filtered_messages['date'].tolist())

        # Extract unique Spotify song links
        track_original_urls_list = (
            filtered_messages
            .explode('spotify_song_links')['spotify_song_links']
            .unique()
            .tolist()
        )
        logging.debug("Number of unique Spotify track URLs (before filtering):", len(track_original_urls_list))
        if track_original_urls_list:
            logging.debug("Sample Spotify URLs:", track_original_urls_list[:3])

        # Only keep URLs that are tracks
        track_urls = []
        track_url_to_first_date = {}
        for url in track_original_urls_list:
            _, _, entity_type = sdm.normalize_and_extract_id(url)
            if entity_type == 'track':
                track_urls.append(url)
        # Map each normalized track URL to its earliest date in the filtered messages
        for url in track_urls:
            # Find all message dates for this URL
            dates = filtered_messages[filtered_messages['spotify_song_links'].apply(lambda links: url in links if isinstance(links, list) else False)]['date']
            if not dates.empty:
                first_date = min(dates)
                normalized_url, _, _ = sdm.normalize_and_extract_id(url)
                track_url_to_first_date[normalized_url] = first_date
        # Sort normalized URLs by their first date
        sorted_normalized_urls = [url for url, _ in sorted(track_url_to_first_date.items(), key=lambda x: x[1])]
        logging.debug("Sorted normalized track URLs by first date:", sorted_normalized_urls[:3])

        result = {
            'status': 'success',
            'playlist_name': playlist_name,
            'tracks_processed': len(sorted_normalized_urls),
            'errors': [],
            'selected_chats': selected_chat_names
        }

        # Use sorted_normalized_urls for cache lookup and playlist creation
        result['tracks_processed'] = len(sorted_normalized_urls)
        
        if not sorted_normalized_urls:
            logging.warning(f"No Spotify tracks found for selected chats in date range {start_date} to {end_date}")
            result['status'] = 'warning'
            result['errors'].append(f"No Spotify tracks found for the selected chats in the specified date range ({start_date} to {end_date})")
            return result

        # Step 3: Create Spotify playlist using existing web session tokens
        try:
            logging.info(f"Creating Spotify playlist with {len(sorted_normalized_urls)} tracks...")
            
            # Use existing tokens from web session instead of creating new OAuth flow
            spotify_client = spotipy.Spotify(auth=access_token)
            
            # Get user ID
            user = spotify_client.current_user()
            user_id = user['id']
            
            # Use existing playlist if provided, otherwise find or create
            if existing_playlist_id:
                playlist = spotify_client.playlist(existing_playlist_id)
                logging.info(f"Adding tracks to existing playlist: {playlist['name']} ({existing_playlist_id})")
            else:
                playlist = csp.find_or_create_playlist(spotify_client, user_id, playlist_name, public=True)
            
            # Get track IDs from normalized URLs
            logging.info(f"Looking up track IDs for {len(sorted_normalized_urls)} normalized track URLs...")
            logging.info(f"Sample normalized track URLs: {sorted_normalized_urls[:3] if sorted_normalized_urls else []}")
            track_ids = csp.get_song_ids_from_cached_urls(sorted_normalized_urls)
            logging.info(f"Found {len(track_ids)} track IDs from cache")
            logging.info(f"Sample track IDs: {track_ids[:3] if track_ids else []}")
            
            if track_ids:
                # Add tracks to playlist and get number of new tracks actually added
                num_songs_added = csp.add_tracks_to_playlist(spotify_client, playlist['id'], track_ids)
                logging.info(f"Successfully added {num_songs_added} new tracks to playlist '{playlist_name}'")

                # --- Contributor stats ---
                # 1. For this update (month):
                #    For each new track added, find the sender(s) of the message(s) that shared it in the last 30 days.
                # 2. For all time: For each track ever added to the playlist, find the sender(s) who shared it.
                #
                # We'll use the filtered_messages DataFrame for the current update, and messages_df for all time.
                #
                # Get sender mapping for new tracks in this update (month)
                new_track_set = set(track_ids)
                one_month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
                filtered_recent = filtered_messages[filtered_messages['date'] >= one_month_ago]
                month_contrib = {}
                for idx, row in filtered_recent.iterrows():
                    links = row['spotify_song_links']
                    sender = row.get('sender_handle_id')
                    if not isinstance(links, list) or not sender:
                        continue
                    for url in links:
                        norm_url, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                        if entity_type == 'track' and spotify_id in new_track_set:
                            # Get sender name
                            sender_name = None
                            handles_df = cached_data.get('handles')
                            contacts_df = cached_data.get('contacts')
                            if handles_df is not None:
                                handle_row = handles_df[handles_df['handle_id'] == sender]
                                if not handle_row.empty:
                                    contact_info = handle_row.iloc[0].get('contact_info')
                                    if contacts_df is not None and contact_info:
                                        contact_row = contacts_df[contacts_df['phone_number'] == contact_info]
                                        if not contact_row.empty:
                                            first = contact_row.iloc[0].get('first_name') or ''
                                            last = contact_row.iloc[0].get('last_name') or ''
                                            sender_name = f"{first} {last}".strip()
                                    if not sender_name and contact_info:
                                        sender_name = str(contact_info)
                            if not sender_name:
                                sender_name = f"User {sender}"
                            month_contrib[sender_name] = month_contrib.get(sender_name, 0) + 1
                # All-time contributors for all tracks ever added to the playlist
                all_contrib = {}
                all_track_set = set(track_ids)
                for idx, row in filtered_messages.iterrows():
                    links = row['spotify_song_links']
                    sender = row.get('sender_handle_id')
                    if not isinstance(links, list) or not sender:
                        continue
                    for url in links:
                        norm_url, spotify_id, entity_type = sdm.normalize_and_extract_id(url)
                        if entity_type == 'track' and spotify_id in all_track_set:
                            # Get sender name
                            sender_name = None
                            handles_df = cached_data.get('handles')
                            contacts_df = cached_data.get('contacts')
                            if handles_df is not None:
                                handle_row = handles_df[handles_df['handle_id'] == sender]
                                if not handle_row.empty:
                                    contact_info = handle_row.iloc[0].get('contact_info')
                                    if contacts_df is not None and contact_info:
                                        contact_row = contacts_df[contacts_df['phone_number'] == contact_info]
                                        if not contact_row.empty:
                                            first = contact_row.iloc[0].get('first_name') or ''
                                            last = contact_row.iloc[0].get('last_name') or ''
                                            sender_name = f"{first} {last}".strip()
                                    if not sender_name and contact_info:
                                        sender_name = str(contact_info)
                            if not sender_name:
                                sender_name = f"User {sender}"
                            all_contrib[sender_name] = all_contrib.get(sender_name, 0) + 1
                # Format and update description
                today_str = datetime.datetime.now().strftime('%B %d, %Y')
                new_description = format_playlist_description(today_str, num_songs_added, month_contrib, all_contrib)
                logger.warning(f"Playlist description ({len(new_description)} chars):\n{new_description}")
                spotify_client.playlist_change_details(playlist['id'], description=new_description)
                logging.info(f"Updated playlist description: {new_description}")
                result['playlist_description'] = new_description
            else:
                logging.warning("No valid track IDs found to add to playlist")
                result['status'] = 'warning'
                result['errors'].append("No valid Spotify tracks found to add to playlist")
            
            logging.info("Playlist created successfully!")
        except Exception as e:
            logging.error(f"Error creating Spotify playlist: {str(e)}")
            result['status'] = 'error'
            result['errors'].append(f"Playlist creation error: {str(e)}")
            return result

        return result

    except Exception as e:
        logging.error(f"Unexpected error in create_playlist_from_cached_data: {str(e)}")
        return {
            'status': 'error',
            'errors': [f"Unexpected error: {str(e)}"]
        }

@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "Authorization code not provided"}

    # Exchange the authorization code for an access token
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")  # Fetch from environment variables


    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        return {"error": "Failed to exchange authorization code", "details": response.json()}
    
    # Return tokens to the frontend or save them securely in the backend
    tokens = response.json()

    # Save tokens in a session, database, or in-memory store (temporary example)
    user_tokens["access_token"] = tokens["access_token"]
    user_tokens["refresh_token"] = tokens["refresh_token"]
    user_tokens["expires_in"] = tokens["expires_in"]

    # Redirect to the frontend with the "code" parameter
    frontend_url = request.url_for("static", path="index.html")
    return RedirectResponse(url=f"{frontend_url}?code={code}")


@app.get("/user-profile")
async def get_user_profile():
    # Fetch user profile using access token
    access_token = user_tokens.get("access_token")
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Access token not available"})

    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)

    if response.status_code != 200:
        return JSONResponse(
            status_code=response.status_code,
            content={"error": "Failed to fetch user profile", "details": response.json()},
        )

    return response.json()

# Place /user-playlists endpoint here, right after /user-profile
@app.get("/user-playlists")
async def get_user_playlists():
    access_token = user_tokens.get("access_token")
    if not access_token:
        return JSONResponse(status_code=401, content={"error": "Access token not available"})
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)
    if response.status_code != 200:
        return JSONResponse(
            status_code=response.status_code,
            content={"error": "Failed to fetch playlists", "details": response.json()},
        )
    playlists = response.json().get("items", [])
    # Return only name and id for each playlist
    return [{"name": p["name"], "id": p["id"]} for p in playlists]

@app.post("/validate-chat-file/")
async def validate_chat_file(file: UploadFile = File(...)):
    try:
        # Save the uploaded file temporarily
        temp_dir = "/tmp"  # Temporary directory
        temp_file_path = os.path.join(temp_dir, file.filename)

        with open(temp_file_path, "wb") as f:
            f.write(await file.read())

        # Validate the file (check if it exists and its type)
        if not os.path.exists(temp_file_path):
            return JSONResponse(
                status_code=404,
                content={"error": "File upload failed or file not found."}
            )

        # Perform additional checks, e.g., file size or type
        if not file.filename.endswith(".db"):
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid file type. Only '.db' files are allowed."}
            )

        return {"message": "File uploaded successfully.", "filepath": temp_file_path}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    

@app.get("/validate-username")
async def validate_username(username: str):
    # Construct the file path
    file_path = f"/Users/{username}/Library/Messages/chat.db"

    # Check if the file exists
    if not os.path.exists(file_path):
        return JSONResponse(
            status_code=404,
            content={"error": f"File not found for username: {username}"}
        )

    return {
        "message": "File exists",
        "filepath": file_path
        }

@app.get("/chat-search-status")
async def chat_search_status():
    """Get current status of chat search processing"""
    return {
        "is_processing": _processing_status["is_processing"],
        "has_cached_data": _cached_data is not None,
        "progress": _processing_status["progress"]
    }

@app.get("/chat-search-progress")
async def chat_search_progress():
    """Server-Sent Events endpoint for real-time progress updates"""
    
    global _cached_data, _processing_status
    
    # Simple check - if data exists, return immediately
    if _cached_data is not None:
        async def cached_data_stream():
            yield f"data: {json.dumps({'status': 'cached', 'message': 'Using cached data'})}\n\n"
        return StreamingResponse(cached_data_stream(), media_type="text/event-stream")
    
    # If already processing, return status
    if _processing_status["is_processing"]:
        async def already_processing_stream():
            yield f"data: {json.dumps({'status': 'already_processing', 'message': 'Data processing already in progress'})}\n\n"
        return StreamingResponse(already_processing_stream(), media_type="text/event-stream")
    
    # Start new processing
    async def new_processing_stream():
        _processing_status["is_processing"] = True
        
        try:
            messages_db_path = uf.get_messages_db_path()
            
            yield f"data: {json.dumps({'status': 'starting', 'message': 'Starting data processing...'})}\n\n"
            await asyncio.sleep(0.1)
            
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Connecting to database...'})}\n\n"
            await asyncio.sleep(0.5)
            
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Pulling messages from database... (8-10 seconds)'})}\n\n"
            await asyncio.sleep(1)
            
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Processing data... This will take about 40-50 seconds total.'})}\n\n"
            await asyncio.sleep(1)
            
            # Run the actual processing
            start_time = time.time()
            loop = asyncio.get_event_loop()
            global _cached_data
            _cached_data = await loop.run_in_executor(None, prepare_data_main.pull_and_clean_messages, messages_db_path)
            
            # Initialize and populate Spotify URL cache
            yield f"data: {json.dumps({'status': 'progress', 'message': 'Processing Spotify URLs and caching metadata...'})}\n\n"
            await asyncio.sleep(0.1)
            
            try:
                from dopetracks.processing.spotify_interaction import spotify_db_manager as sdm
                sdm.main(_cached_data['messages'], 'all_spotify_links')
                yield f"data: {json.dumps({'status': 'progress', 'message': 'Spotify URL cache populated successfully!'})}\n\n"
            except Exception as e:
                logging.error(f"Error processing Spotify URLs: {str(e)}")
                yield f"data: {json.dumps({'status': 'error', 'message': f'Error processing Spotify URLs: {str(e)}'})}\n\n"
                raise
            
            total_time = time.time() - start_time
            
            yield f"data: {json.dumps({'status': 'completed', 'message': f'Data processing completed in {total_time:.1f} seconds! Chat search is now ready.'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'Error during processing: {str(e)}'})}\n\n"
            logging.error(f"Error in chat search progress: {str(e)}")
        finally:
            _processing_status["is_processing"] = False
    
    return StreamingResponse(new_processing_stream(), media_type="text/event-stream")

@app.get("/chat-search")
async def chat_search(query: str):
    """Search chat database by chat names AND participant names"""
    global _cached_data
    
    try:
        logging.info(f"Chat search requested for: '{query}'")
        
        if not query.strip():
            return []
        
        # Check if data is being processed
        if _processing_status["is_processing"]:
            return {"status": "processing", "message": "Data is currently being processed. Please wait..."}
        
        # If no cached data, return status indicating processing is needed
        if _cached_data is None:
            return {"status": "needs_processing", "message": "Data processing required. Please initiate processing first."}
        
        messages_df = _cached_data['messages']
        contacts_df = _cached_data['contacts']
        
        # Create a mapping of contact_info to names for easier lookup
        contacts_lookup = {}
        if contacts_df is not None and not contacts_df.empty:
            for _, contact in contacts_df.iterrows():
                phone = contact.get('phone_number', '')
                first_name = contact.get('first_name', '')
                last_name = contact.get('last_name', '')
                if phone:
                    full_name = f"{first_name} {last_name}".strip()
                    if full_name:
                        contacts_lookup[phone] = full_name
        
        # Get unique chats with their participant info
        chat_info = messages_df.groupby('chat_name').agg({
            'chat_members_contact_info': 'first',  # Get participant contact info
            'sender_handle_id': 'nunique',  # Number of unique senders (members)
            'message_id': 'count',  # Total messages in this chat
            'spotify_song_links': lambda x: sum(len(links) for links in x if isinstance(links, list))
        }).reset_index()
        
        # Filter chats based on chat name OR participant names
        matching_chats = []
        
        for _, chat in chat_info.iterrows():
            chat_name = chat['chat_name'] if pd.notna(chat['chat_name']) else ''
            participants_contact_info = chat['chat_members_contact_info']
            
            # Check if query matches chat name
            chat_name_match = query.lower() in chat_name.lower() if chat_name else False
            
            # Check if query matches any participant names
            participant_name_match = False
            participant_names = []
            
            if isinstance(participants_contact_info, (list, tuple)) and len(participants_contact_info) > 0:
                for contact_info in participants_contact_info:
                    if contact_info in contacts_lookup:
                        name = contacts_lookup[contact_info]
                        participant_names.append(name)
                        if query.lower() in name.lower():
                            participant_name_match = True
                    else:
                        # If no contact name, use the contact info (phone number)
                        if contact_info and query.lower() in str(contact_info).lower():
                            participant_name_match = True
                        participant_names.append(contact_info or "Unknown")
            
            # Include chat if either chat name or participant matches
            if chat_name_match or participant_name_match:
                # Create a descriptive name for the chat
                display_name = chat_name
                if not display_name or display_name.strip() == '':
                    # For chats without names, show participant names
                    if len(participant_names) <= 3:
                        display_name = ", ".join(participant_names)
                    else:
                        display_name = f"{', '.join(participant_names[:2])}, +{len(participant_names)-2} others"
                
                matching_chats.append({
                    'original_chat_name': chat_name,
                    'display_name': display_name,
                    'members': chat['sender_handle_id'],
                    'total_messages': chat['message_id'],
                    'urls': chat['spotify_song_links'],
                    'participant_names': participant_names
                })
        
        if len(matching_chats) == 0:
            return []
        
        # Calculate user's personal message count for matching chats
        for chat in matching_chats:
            original_name = chat['original_chat_name']
            user_messages = messages_df[
                (messages_df['chat_name'] == original_name) & 
                (messages_df['sender_handle_id'] == 1)
            ]['message_id'].count()
            chat['user_messages'] = int(user_messages)

            # Find the date of the most recent Spotify song link in this chat
            chat_messages = messages_df[(messages_df['chat_name'] == original_name)]
            # Filter to messages with at least one Spotify link
            chat_messages_with_links = chat_messages[chat_messages['spotify_song_links'].apply(lambda x: isinstance(x, list) and len(x) > 0)]
            if not chat_messages_with_links.empty:
                most_recent_date = chat_messages_with_links['date'].max()
                chat['most_recent_song_date'] = most_recent_date
            else:
                chat['most_recent_song_date'] = None
        
        # Sort by total messages (most active chats first) and limit results
        matching_chats.sort(key=lambda x: x['total_messages'], reverse=True)
        result = matching_chats[:20]
        
        # Format for frontend (remove internal fields)
        formatted_result = []
        for chat in result:
            formatted_result.append({
                'name': chat['display_name'],
                'members': chat['members'],
                'total_messages': chat['total_messages'],
                'user_messages': chat['user_messages'],
                'urls': chat['urls'],
                'most_recent_song_date': chat.get('most_recent_song_date')
            })
        
        logging.info(f"Found {len(formatted_result)} chats matching '{query}' (including participant search)")
        return formatted_result
        
    except Exception as e:
        logging.error(f"Error in chat search: {str(e)}")
        return []

# TODO: Future optimized chat search - uncomment and use when ready
# async def chat_search_optimized(query: str):
#     """Optimized chat search using direct SQL query"""
#     import sqlite3
#     
#     try:
#         messages_db_path = uf.get_messages_db_path()
#         
#         # Direct SQL query to get chat statistics quickly
#         conn = sqlite3.connect(messages_db_path)
#         cursor = conn.cursor()
#         
#         # Query to get chat names with message counts
#         sql_query = """
#         SELECT 
#             c.display_name as chat_name,
#             COUNT(DISTINCT cmj.handle_id) as member_count,
#             COUNT(m.text) as message_count
#         FROM chat c
#         JOIN chat_message_join cmj ON c.ROWID = cmj.chat_id
#         JOIN message m ON cmj.message_id = m.ROWID
#         WHERE c.display_name IS NOT NULL 
#         AND c.display_name LIKE ?
#         GROUP BY c.display_name
#         ORDER BY message_count DESC
#         LIMIT 20
#         """
#         
#         cursor.execute(sql_query, (f'%{query}%',))
#         results = cursor.fetchall()
#         conn.close()
#         
#         # Format results for frontend
#         chat_list = []
#         for row in results:
#             chat_list.append({
#                 "name": row[0],
#                 "members": row[1],
#                 "urls": 0  # Would need separate query for Spotify URLs
#             })
#         
#         return chat_list
#         
#     except Exception as e:
#         logging.error(f"Error in optimized chat search: {str(e)}")
#         return []

# Serve static files (like index.html)
app.mount("/", StaticFiles(directory="website", html=True), name="static")

# print("SPOTIFY_CLIENT_ID:", os.getenv("SPOTIFY_CLIENT_ID"))
# print("Registered routes:", app.routes)
