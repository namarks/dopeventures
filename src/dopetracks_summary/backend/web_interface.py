
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import requests
import os

# Spotify credentials from environment variables
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8888/callback"

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serve the index.html file for the root route."""
    index_path = os.path.join("frontend", "index.html")
    with open(index_path, "r") as file:
        return HTMLResponse(content=file.read())


@app.get("/callback")
def spotify_callback(code: str):
    """Handle Spotify's OAuth callback."""
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(token_url, data=payload, headers=headers)
    if response.status_code == 200:
        token_data = response.json()
        # Save or return tokens as needed
        return JSONResponse(content=token_data)
    else:
        return JSONResponse(status_code=response.status_code, content={"error": response.text})


@app.post("/upload-chat/")
async def upload_chat(
    file: UploadFile,
    start_date: str = Form(...),
    end_date: str = Form(...),
    playlist_name: str = Form(...),
    chat_name_text: str = Form(None)  # Optional filter for chat name
):
    """Handle file uploads and process data."""
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    try:
        # Call your core logic to process the file
        # Replace with the correct call to your processing function
        result = {"message": "Processing successful!", "playlist_name": playlist_name}
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        os.remove(file_path)
