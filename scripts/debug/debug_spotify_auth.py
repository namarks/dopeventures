#!/usr/bin/env python3
"""
Comprehensive Spotify OAuth debugging script.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

print("="*70)
print("SPOTIFY OAUTH COMPREHENSIVE DEBUG")
print("="*70)

# 1. Configuration Check
print("\n1. CONFIGURATION CHECK")
print("-" * 70)
print(f"Client ID: {'✅ Set' if client_id else '❌ NOT SET'}")
if client_id:
    print(f"   Value: {client_id[:10]}...{client_id[-4:] if len(client_id) > 14 else client_id}")
print(f"Client Secret: {'✅ Set' if client_secret else '❌ NOT SET'}")
print(f"Redirect URI: {redirect_uri}")

# 2. Redirect URI Validation
print("\n2. REDIRECT URI VALIDATION")
print("-" * 70)
issues = []
if "localhost" in redirect_uri:
    issues.append("❌ Contains 'localhost' - Spotify requires 127.0.0.1")
    print("❌ ISSUE: Contains 'localhost'")
    print("   Spotify doesn't allow localhost - must use 127.0.0.1")
    print(f"   Current: {redirect_uri}")
    print(f"   Should be: {redirect_uri.replace('localhost', '127.0.0.1')}")
elif "127.0.0.1" not in redirect_uri:
    issues.append("⚠️  Not using 127.0.0.1 - may not work with Spotify")
    print("⚠️  WARNING: Not using 127.0.0.1")
else:
    print("✅ Using 127.0.0.1 (correct)")

if redirect_uri.endswith('/'):
    issues.append("❌ Has trailing slash")
    print("❌ ISSUE: Has trailing slash")
    print(f"   Current: {redirect_uri}")
    print(f"   Should be: {redirect_uri.rstrip('/')}")
else:
    print("✅ No trailing slash (correct)")

if "https://" in redirect_uri and "127.0.0.1" in redirect_uri:
    issues.append("⚠️  Using https:// with 127.0.0.1 (should use http://)")
    print("⚠️  WARNING: Using https:// with 127.0.0.1")
    print("   Should use http:// for localhost/127.0.0.1")
else:
    print("✅ Using http:// (correct for localhost)")

# 3. Spotify Dashboard Checklist
print("\n3. SPOTIFY DASHBOARD CHECKLIST")
print("-" * 70)
print("Go to: https://developer.spotify.com/dashboard")
print("\nRequired steps:")
print(f"  [ ] App selected (Client ID matches: {client_id[:10]}... if client_id else 'N/A')")
print(f"  [ ] 'Edit Settings' clicked")
print(f"  [ ] Redirect URI added: {redirect_uri}")
print(f"  [ ] 'Add' button clicked")
print(f"  [ ] 'Save' button clicked at bottom")
print(f"  [ ] Waited 1-2 minutes for changes to propagate")

# 4. Common Errors
print("\n4. COMMON ERRORS & SOLUTIONS")
print("-" * 70)

print("\n❌ 'INVALID_CLIENT: Insecure redirect URI'")
print("   Cause: Redirect URI not in Dashboard or doesn't match exactly")
print("   Fix:")
print(f"      1. Add '{redirect_uri}' to Spotify Dashboard")
print("      2. Make sure it matches EXACTLY (no trailing slash, correct protocol)")
print("      3. Click 'Save'")
print("      4. Wait 1-2 minutes")

print("\n❌ '401 Unauthorized' on /callback")
print("   Cause: Not logged into the app")
print("   Fix:")
print("      1. Go to http://127.0.0.1:8888/")
print("      2. Register or login")
print("      3. THEN click 'Authorize Spotify'")

print("\n❌ 'Failed to exchange authorization code'")
print("   Cause: Redirect URI mismatch between request and token exchange")
print("   Fix:")
print("      1. Make sure .env has correct redirect URI")
print("      2. Restart server after changing .env")
print("      3. Clear browser cache and try again")

print("\n❌ Login works in Cursor but not external browser")
print("   Cause: Cookie/CORS issues")
print("   Fix:")
print("      1. Make sure accessing via http://127.0.0.1:8888 (not localhost)")
print("      2. Clear cookies for 127.0.0.1:8888")
print("      3. Check browser privacy settings")
print("      4. Try disabling browser extensions")

# 5. Testing Steps
print("\n5. TESTING STEPS")
print("-" * 70)
print("1. ✅ Configuration verified (run this script)")
print("2. [ ] Spotify Dashboard updated")
print("3. [ ] Server restarted")
print("4. [ ] Access app via http://127.0.0.1:8888/")
print("5. [ ] Register or login")
print("6. [ ] Click 'Authorize Spotify'")
print("7. [ ] Complete Spotify authorization")
print("8. [ ] Should redirect back successfully")

# 6. Debug Commands
print("\n6. DEBUG COMMANDS")
print("-" * 70)
print("Check server logs for:")
print("  - 'OAuth request - Client ID: ... Redirect URI: ...'")
print("  - 'Exchanging Spotify authorization code for tokens'")
print("  - 'Spotify tokens stored for user ...'")
print("\nCheck browser console (F12) for:")
print("  - 'Using redirect URI: ...'")
print("  - 'Full Auth URL: ...'")
print("  - Any CORS or network errors")

if issues:
    print("\n" + "="*70)
    print("⚠️  ISSUES FOUND - FIX THESE FIRST:")
    print("="*70)
    for issue in issues:
        print(f"  {issue}")
else:
    print("\n" + "="*70)
    print("✅ CONFIGURATION LOOKS GOOD!")
    print("="*70)
    print("\nIf authorization still fails:")
    print("  1. Double-check Spotify Dashboard has exact redirect URI")
    print("  2. Make sure you're logged into the app first")
    print("  3. Check browser console and server logs for specific errors")

print("\n" + "="*70)
