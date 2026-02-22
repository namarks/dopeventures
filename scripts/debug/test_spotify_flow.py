#!/usr/bin/env python3
"""
Test script to debug Spotify OAuth flow.
Shows what redirect URI is being used and helps identify issues.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

client_id = os.getenv("SPOTIFY_CLIENT_ID")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

print("="*60)
print("SPOTIFY OAUTH FLOW TEST")
print("="*60)

print(f"\n1. Client ID: {client_id}")
print(f"2. Redirect URI: {redirect_uri}")

print("\n" + "="*60)
print("TEST AUTHORIZATION URL")
print("="*60)

scope = "playlist-modify-public playlist-modify-private"

# Fetch state and PKCE params from the backend (if running)
import requests
try:
    resp = requests.get("http://127.0.0.1:8888/get-client-id", timeout=3).json()
    state = resp.get("state", "")
    code_challenge = resp.get("code_challenge", "")
    code_challenge_method = resp.get("code_challenge_method", "S256")
    print(f"   State token: {state[:16]}...")
    print(f"   PKCE challenge: {code_challenge[:16]}...")
except Exception:
    state = ""
    code_challenge = ""
    code_challenge_method = ""
    print("   (Backend not running — state/PKCE params unavailable)")

auth_url = (
    f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}"
    f"&scope={scope}&redirect_uri={redirect_uri}"
    f"&state={state}&code_challenge={code_challenge}&code_challenge_method={code_challenge_method}"
)

print(f"\nFull Authorization URL:")
print(auth_url)

print("\n" + "="*60)
print("CHECKLIST")
print("="*60)

print("\n1. Is redirect URI in Spotify Dashboard?")
print(f"   Go to: https://developer.spotify.com/dashboard")
print(f"   Check that this URI is listed: {redirect_uri}")

print("\n2. Are you logged into the app?")
print("   The /callback endpoint requires authentication")
print("   Make sure you're logged in before clicking 'Authorize Spotify'")

print("\n3. What happens when you click 'Authorize Spotify'?")
print("   - Does it redirect to Spotify? ✓")
print("   - Do you see the authorization page? ✓")
print("   - After clicking 'Agree', where does it redirect?")
print("   - Do you see an error page or the success page?")

print("\n4. Check browser console (F12):")
print("   - Look for any JavaScript errors")
print("   - Check Network tab for failed requests")
print("   - See what redirect_uri is actually being sent")

print("\n5. Check server logs:")
print("   - Look for errors when /callback is called")
print("   - Check if token exchange succeeds or fails")
print("   - Look for 'Spotify token exchange failed' messages")

print("\n" + "="*60)
print("COMMON ISSUES")
print("="*60)

print("\n❌ 'INVALID_CLIENT: Insecure redirect URI'")
print("   → Redirect URI not in Spotify Dashboard")
print("   → Redirect URI doesn't match exactly")

print("\n❌ '401 Unauthorized' on /callback")
print("   → User not logged in when Spotify redirects back")
print("   → Session expired")

print("\n❌ 'Failed to exchange authorization code'")
print("   → Redirect URI mismatch between request and token exchange")
print("   → Authorization code already used (expired)")

print("\n❌ Redirects to /index.html but status doesn't update")
print("   → Frontend not checking auth status after redirect")
print("   → Need to refresh page or check status manually")
