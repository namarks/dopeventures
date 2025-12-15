#!/usr/bin/env python3
"""
Debug script to check Spotify OAuth configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
else:
    print(f"⚠️  No .env file found at: {env_path}")
    print("   Loading from environment variables...")

# Check configuration
print("\n" + "="*60)
print("SPOTIFY OAUTH CONFIGURATION CHECK")
print("="*60)

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

print(f"\n1. SPOTIFY_CLIENT_ID:")
if client_id:
    print(f"   ✅ Set: {client_id[:10]}...{client_id[-4:] if len(client_id) > 14 else client_id}")
else:
    print("   ❌ NOT SET")

print(f"\n2. SPOTIFY_CLIENT_SECRET:")
if client_secret:
    print(f"   ✅ Set: {client_secret[:10]}...{client_secret[-4:] if len(client_secret) > 14 else client_secret}")
else:
    print("   ❌ NOT SET")

print(f"\n3. SPOTIFY_REDIRECT_URI:")
print(f"   Current: {redirect_uri}")

# Check for common issues
print("\n" + "="*60)
print("COMMON ISSUES CHECK")
print("="*60)

issues = []

if not client_id:
    issues.append("❌ SPOTIFY_CLIENT_ID is not set")
if not client_secret:
    issues.append("❌ SPOTIFY_CLIENT_SECRET is not set")

if redirect_uri.endswith('/'):
    issues.append("⚠️  Redirect URI has trailing slash (should not)")
    print(f"   Current: {redirect_uri}")
    print(f"   Should be: {redirect_uri.rstrip('/')}")

if 'https://' in redirect_uri and 'localhost' in redirect_uri:
    issues.append("⚠️  Using https:// with localhost (should use http://)")
    print(f"   Current: {redirect_uri}")
    print(f"   Should be: {redirect_uri.replace('https://', 'http://')}")

if redirect_uri != "http://localhost:8888/callback":
    print(f"\n⚠️  Redirect URI is not the default")
    print(f"   Current: {redirect_uri}")
    print(f"   Default: http://localhost:8888/callback")
    print(f"   Make sure this matches your Spotify Developer Dashboard!")

if issues:
    print("\n⚠️  ISSUES FOUND:")
    for issue in issues:
        print(f"   {issue}")
else:
    print("\n✅ No obvious configuration issues found!")

print("\n" + "="*60)
print("SPOTIFY DEVELOPER DASHBOARD CHECKLIST")
print("="*60)
print("\nGo to: https://developer.spotify.com/dashboard")
print("\n1. Click on your app")
print("2. Click 'Edit Settings'")
print("3. Under 'Redirect URIs', make sure you have:")
print(f"   {redirect_uri}")
print("\n4. Click 'Add' if adding new URI")
print("5. Click 'Save'")
print("\n6. Verify Client ID matches:")
if client_id:
    print(f"   {client_id}")
else:
    print("   ❌ Client ID not set in .env")

print("\n" + "="*60)
print("TESTING")
print("="*60)
print("\nTo test the OAuth flow:")
print("1. Make sure server is running: python3 start_multiuser.py")
print("2. Open browser to: http://localhost:8888/")
print("3. Click 'Authorize Spotify'")
print("4. Check browser console (F12) for any errors")
print("5. Check server logs for redirect URI being used")

print("\n" + "="*60)
print("DEBUGGING TIPS")
print("="*60)
print("\nIf you still get 'INVALID_CLIENT: Insecure redirect URI':")
print("1. Verify redirect URI in Spotify Dashboard matches exactly")
print("2. Make sure no trailing slash")
print("3. For localhost, use http:// not https://")
print("4. Restart server after changing .env file")
print("5. Clear browser cache and cookies")
print("6. Check browser console (F12) → Network tab to see actual redirect URI sent")
