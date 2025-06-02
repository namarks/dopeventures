from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dopetracks.frontend_interface.core_logic import process_user_inputs
import os
import requests
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, set this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_tokens = {}

class ProcessRequest(BaseModel):
    start_date: str
    end_date: str
    playlist_name: str
    filepath: Optional[str] = None
    chat_name_text: Optional[str] = None

@app.post("/process")
async def process(request: ProcessRequest):
    try:
        process_user_inputs(
            start_date=request.start_date,
            end_date=request.end_date,
            playlist_name=request.playlist_name,
            filepath=request.filepath,
            chat_name_text=request.chat_name_text
        )
        return {"success": True, "message": "Process completed successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-client-id")
async def get_client_id():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    if not client_id:
        return JSONResponse(status_code=500, content={"error": "SPOTIFY_CLIENT_ID is not set"})
    return {"client_id": client_id}

@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return {"error": "Authorization code not provided"}

    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

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
    tokens = response.json()
    user_tokens["access_token"] = tokens["access_token"]
    user_tokens["refresh_token"] = tokens["refresh_token"]
    user_tokens["expires_in"] = tokens["expires_in"]
    # You may want to redirect to your frontend here
    return {"message": "Authorization successful", "tokens": tokens}

@app.get("/user-profile")
async def get_user_profile():
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888) 