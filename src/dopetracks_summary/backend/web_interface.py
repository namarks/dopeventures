from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv
import requests

import logging
logger = logging.getLogger("uvicorn.error")




# Load environment variables
load_dotenv()

app = FastAPI()

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
    chat_name_text: str = Form(None),
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

        # Process the file (placeholder logic)
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        processed_file_path = os.path.join(upload_dir, f"{username}_chat.db")
        with open(processed_file_path, "wb") as f:
            f.write(file_content)

        return {"message": "File processed successfully.", "playlist": playlist_name}
    except Exception as e:
        logger.error(f"Debug Info: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "Authorization code not provided"}

    # Exchange the authorization code for an access token
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = "http://localhost:8888/callback"

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

# Serve static files (like index.html)
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

# print("SPOTIFY_CLIENT_ID:", os.getenv("SPOTIFY_CLIENT_ID"))
# print("Registered routes:", app.routes)
