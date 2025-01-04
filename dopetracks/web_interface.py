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
from dopetracks.core_logic import processs_user_inputs
from queue import SimpleQueue


# Load environment variables
load_dotenv()

app = FastAPI()
port = int(os.getenv("PORT", 8888))  # Default to 8888 if PORT is not set

# Temporary in-memory token store (use a database in production)
user_tokens = {}

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


@app.post("/upload-chat/")
async def upload_chat(
    username: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    playlist_name: str = Form(...),
    chat_name_text: Optional[str]= Form(None),
):

    try:
        # Dynamically construct the file path
        file_path = f"/Users/{username}/Library/Messages/chat.db"
        
        # Check if the file exists
        if not os.path.exists(file_path):
            return JSONResponse(
                status_code=404,
                content={"error": f"File not found at {file_path}. Ensure the username is correct."},
            )

        # Read the file (or process it as needed)
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Call the core logic function to process inputs and create a playlist
        logging.info(f"Processing chat data for playlist: {playlist_name}")

        processs_user_inputs(
            start_date=start_date,
            end_date=end_date,
            playlist_name=playlist_name,
            filepath=file_path,
            chat_name_text=chat_name_text,
        )
             
        return {"message": "File processed successfully.", "playlist": playlist_name}
    
    except Exception as e:
        error_message = f"An error occurred while creating the playlist: {str(e)}"
        logging.error(error_message)
        return JSONResponse(status_code=500, content={"error": str(e)})
    
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

@app.get("/chat-search")
async def chat_search(query: str):
    # Example: Search chat database for matching group names
    # Replace this with actual database query logic
    return [
        {"name": "dope tracks", "members": 7, "urls": 31},
        {"name": "music lovers", "members": 5, "urls": 20}
    ]


# Serve static files (like index.html)
app.mount("/", StaticFiles(directory="website", html=True), name="static")

# print("SPOTIFY_CLIENT_ID:", os.getenv("SPOTIFY_CLIENT_ID"))
# print("Registered routes:", app.routes)
