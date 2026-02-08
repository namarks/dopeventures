#!/usr/bin/env python3
"""
Final verification script for Spotify OAuth setup.
Checks everything before attempting authorization.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Try to import settings
try:
    sys.path.insert(0, str(Path(__file__).parent / "packages"))
    from dopetracks.config import settings
except Exception as e:
    print(f"Error importing settings: {e}")
    settings = None

print("="*70)
print("SPOTIFY OAUTH FINAL VERIFICATION")
print("="*70)

# Check .env file
print("\n1. .ENV FILE CHECK")
print("-" * 70)
redirect_uri_env = os.getenv("SPOTIFY_REDIRECT_URI")
print(f"SPOTIFY_REDIRECT_URI in .env: {redirect_uri_env}")

if "localhost" in redirect_uri_env:
    print("❌ ERROR: Contains 'localhost' - Spotify doesn't allow this!")
    print("   Must use: http://127.0.0.1:8888/callback")
    sys.exit(1)
elif "127.0.0.1" not in redirect_uri_env:
    print("❌ ERROR: Doesn't contain '127.0.0.1'")
    print("   Must use: http://127.0.0.1:8888/callback")
    sys.exit(1)
else:
    print("✅ Correct format")

# Check settings object
if settings:
    print("\n2. SETTINGS OBJECT CHECK")
    print("-" * 70)
    redirect_uri_settings = settings.SPOTIFY_REDIRECT_URI
    print(f"settings.SPOTIFY_REDIRECT_URI: {redirect_uri_settings}")
    
    if redirect_uri_env != redirect_uri_settings:
        print("❌ MISMATCH: .env and settings don't match!")
        print(f"   .env: {redirect_uri_env}")
        print(f"   settings: {redirect_uri_settings}")
        print("   → Server needs to be restarted to load new .env values")
        sys.exit(1)
    else:
        print("✅ Match")
    
    if "localhost" in redirect_uri_settings:
        print("❌ ERROR: Settings still has 'localhost'!")
        print("   → Server needs to be restarted")
        sys.exit(1)

# Expected value
expected = "http://127.0.0.1:8888/callback"
print("\n3. EXPECTED VALUE")
print("-" * 70)
print(f"Expected: {expected}")

if redirect_uri_env != expected:
    print(f"❌ MISMATCH!")
    print(f"   Current: {redirect_uri_env}")
    print(f"   Expected: {expected}")
    sys.exit(1)
else:
    print("✅ Matches expected value")

# Spotify Dashboard checklist
print("\n4. SPOTIFY DASHBOARD CHECKLIST")
print("-" * 70)
print("Go to: https://developer.spotify.com/dashboard")
print("\nVerify:")
print(f"  [ ] Your app is selected")
print(f"  [ ] 'Edit Settings' is clicked")
print(f"  [ ] Redirect URIs section shows:")
print(f"      {expected}")
print(f"  [ ] 'Save' button was clicked")
print(f"  [ ] Waited 1-2 minutes after saving")

print("\n5. SERVER RESTART CHECK")
print("-" * 70)
print("Make sure server was restarted AFTER updating .env file")
print("Environment variables are only loaded at server startup")

print("\n" + "="*70)
print("✅ ALL CHECKS PASSED!")
print("="*70)
print("\nIf authorization still fails:")
print("  1. Check browser console (F12) - see what redirect_uri is being sent")
print("  2. Check server logs - see what redirect_uri backend is returning")
print("  3. Verify Spotify Dashboard has EXACT match (copy-paste to be sure)")
print("  4. Try clearing browser cache and cookies")
