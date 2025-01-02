from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Spotify credentials from .env
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# In-memory token storage (use a database in production)
user_tokens = {}

# FastAPI app
app = FastAPI()

# Scopes for Spotify API access
SCOPES = "user-read-playback-state user-read-currently-playing playlist-modify-public"

@app.get("/")
def home():
    """Home endpoint to test server status."""
    return {"message": "Spotify Authorization Server is running"}

@app.get("/login")
def login():
    """Redirect users to Spotify's authorization page."""
    spotify_auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES}"
    )
    return RedirectResponse(url=spotify_auth_url, status_code=307)

@app.get("/callback")
def callback(code: str):
    """Handle Spotify's callback and exchange the code for an access token."""
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
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    # Extract token data
    token_data = response.json()

    # Store the tokens in memory (replace with a database in production)
    user_tokens["access_token"] = token_data.get("access_token")
    user_tokens["refresh_token"] = token_data.get("refresh_token")
    user_tokens["expires_in"] = token_data.get("expires_in")

    # Redirect to success page
    return RedirectResponse(url="/success", status_code=302)

@app.get("/success")
def success():
    """Success page after login."""
    return HTMLResponse(content="""
    <html>
        <head><title>Spotify Login Success</title></head>
        <body>
            <h1>Login Successful!</h1>
            <p>You are now logged in with Spotify. You can start using the app.</p>
        </body>
    </html>
    """)

@app.get("/profile")
def profile():
    """Get user's Spotify profile using the access token."""
    access_token = user_tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="User is not logged in or access token is missing")

    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return response.json()

@app.post("/refresh-token")
def refresh_token(refresh_token: str = None):
    """Use the refresh token to get a new access token."""
    if not refresh_token:
        refresh_token = user_tokens.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token is required")

    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(token_url, data=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    # Update access token in memory
    token_data = response.json()
    user_tokens["access_token"] = token_data.get("access_token")
    user_tokens["expires_in"] = token_data.get("expires_in")

    return {"message": "Access token refreshed successfully", "access_token": user_tokens["access_token"]}
