import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Load environment variables for Spotify
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")


# print(CLIENT_ID)
logging.critical(f"Client ID: {CLIENT_ID}")
logging.critical(f"Client Secret: {CLIENT_SECRET}")
logging.critical(f"Redirect URI: {REDIRECT_URI}")

