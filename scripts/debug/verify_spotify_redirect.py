#!/usr/bin/env python3
"""
Verify Spotify redirect URI configuration matches what should be in Dashboard.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

print("="*70)
print("SPOTIFY REDIRECT URI VERIFICATION")
print("="*70)

print(f"\n✅ Your .env file has:")
print(f"   SPOTIFY_REDIRECT_URI={redirect_uri}")

print(f"\n📋 ACTION REQUIRED:")
print(f"   Go to: https://developer.spotify.com/dashboard")
print(f"   1. Click on your app")
print(f"   2. Click 'Edit Settings'")
print(f"   3. Under 'Redirect URIs', you MUST have EXACTLY:")
print(f"      {redirect_uri}")
print(f"   4. Click 'Add' if it's not there")
print(f"   5. Click 'Save' at the bottom")

print(f"\n⚠️  IMPORTANT:")
print(f"   - No trailing slash: {redirect_uri} (NOT {redirect_uri}/)")
print(f"   - Use http:// for localhost (NOT https://)")
print(f"   - Must match EXACTLY (case-sensitive, including port)")

print(f"\n🔍 VERIFICATION CHECKLIST:")
print(f"   [ ] Redirect URI in Dashboard: {redirect_uri}")
print(f"   [ ] No trailing slash")
print(f"   [ ] Using http:// (not https://)")
print(f"   [ ] Port is 8888")
print(f"   [ ] Path is /callback (not /callback/)")
print(f"   [ ] Clicked 'Save' in Dashboard")

print(f"\n💡 TIP:")
print(f"   After updating Dashboard, wait 1-2 minutes for changes to propagate")
print(f"   Then try authorizing again")

print("\n" + "="*70)
