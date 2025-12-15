# Spotify OAuth Setup Guide

## The Problem

If you see the error **"INVALID_CLIENT: Insecure redirect URI"**, it means the redirect URI in your code doesn't match what's registered in your Spotify Developer Dashboard.

## Solution

### Step 1: Check Your Current Redirect URI

The redirect URI must match **exactly** in three places:
1. **Spotify Developer Dashboard** (what you registered)
2. **Backend code** (`SPOTIFY_REDIRECT_URI` environment variable)
3. **Frontend code** (what gets sent to Spotify)

### Step 2: Verify Spotify Developer Dashboard

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click on your app
3. Click **"Edit Settings"**
4. Look at **"Redirect URIs"** section
5. Make sure you have: `http://localhost:8888/callback`

**Important:** 
- For localhost, you can use `http://` (not `https://`)
- The URI must match **exactly** including the protocol, port, and path
- You can add multiple redirect URIs (one per line)

### Step 3: Set Environment Variable

Create or update your `.env` file in the project root:

```bash
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

**⚠️ IMPORTANT - Spotify Requirement:**
- **DO NOT use `localhost`** - Spotify doesn't allow it!
- **MUST use `127.0.0.1`** (explicit loopback IP address)
- No trailing slash
- Exact match with Spotify Dashboard
- Uses `http://` for loopback addresses (not `https://`)

**Why?** Spotify's security policy requires explicit loopback IP addresses (`127.0.0.1` or `[::1]`) instead of `localhost` for local development.

### Step 4: Verify Frontend Code

The frontend automatically constructs the redirect URI from `window.location.origin`. This should work, but let's verify:

**Current frontend code** (in `website/script.js`):
```javascript
const redirectUri = window.location.origin + '/callback';
```

This should produce: `http://localhost:8888/callback`

**If you're accessing via a different URL**, you need to either:
- Access via `http://localhost:8888/` (recommended)
- Or update the frontend code to use a fixed redirect URI

### Step 5: Restart Server

After updating `.env`:
```bash
# Stop server (Ctrl+C)
# Restart:
python3 start_multiuser.py
```

## Common Issues

### Issue 1: Mismatch Between Frontend and Backend

**Symptom:** Frontend sends different redirect URI than backend expects

**Fix:** The frontend uses `window.location.origin + '/callback'`, which should match your `.env` file. Make sure:
- You're accessing via `http://localhost:8888/`
- Your `.env` has `SPOTIFY_REDIRECT_URI=http://localhost:8888/callback`

### Issue 2: Redirect URI Not in Spotify Dashboard

**Symptom:** "INVALID_CLIENT: Invalid redirect URI"

**Fix:** 
1. Go to Spotify Developer Dashboard
2. Add `http://localhost:8888/callback` to Redirect URIs
3. Click "Add" and "Save"

### Issue 3: Using `localhost` Instead of `127.0.0.1`

**Symptom:** "INVALID_CLIENT: Insecure redirect URI" or "This redirect URI is not secure"

**Fix:** Spotify doesn't allow `localhost` - you MUST use `127.0.0.1`:
```
✅ http://127.0.0.1:8888/callback
❌ http://localhost:8888/callback
```

**Why?** Spotify requires explicit loopback IP addresses for security. See [Spotify's Redirect URI documentation](https://developer.spotify.com/documentation/web-api/concepts/redirect-uri).

### Issue 4: Trailing Slash

**Symptom:** Redirect works but Spotify rejects it

**Fix:** Make sure there's no trailing slash:
```
✅ http://localhost:8888/callback
❌ http://localhost:8888/callback/
```

## Testing

1. **Check your `.env` file:**
   ```bash
   cat .env | grep SPOTIFY_REDIRECT_URI
   ```
   Should show: `SPOTIFY_REDIRECT_URI=http://localhost:8888/callback`

2. **Check Spotify Dashboard:**
   - Redirect URIs should include: `http://localhost:8888/callback`

3. **Test the flow:**
   - Click "Authorize Spotify" in the frontend
   - Should redirect to Spotify
   - After authorizing, should redirect back to your app
   - Should see "Spotify Authorization Successful!"

## Production Setup

For production, you'll need:

1. **HTTPS redirect URI:**
   ```
   SPOTIFY_REDIRECT_URI=https://yourdomain.com/callback
   ```

2. **Add to Spotify Dashboard:**
   - Add `https://yourdomain.com/callback` to Redirect URIs

3. **Update frontend** (if needed):
   - The frontend uses `window.location.origin`, which should work automatically
   - But you can hardcode it if needed

## Quick Checklist

- [ ] Redirect URI in Spotify Dashboard: `http://127.0.0.1:8888/callback` (NOT localhost!)
- [ ] `.env` file has: `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback`
- [ ] No trailing slash in redirect URI
- [ ] Using `http://` for loopback (not `https://`)
- [ ] Using `127.0.0.1` (NOT `localhost`)
- [ ] Server restarted after updating `.env`
- [ ] Accessing app via `http://localhost:8888/` or `http://127.0.0.1:8888/` (both work for accessing)

## Still Having Issues?

1. **Check browser console** (F12) for errors
2. **Check server logs** for redirect URI being used
3. **Verify Spotify app settings:**
   - Client ID matches
   - Client Secret matches
   - Redirect URI matches exactly
4. **Try clearing browser cache** and cookies
5. **Check network tab** in browser DevTools to see what redirect URI is actually being sent

## See Also

- [Spotify Authorization Guide](https://developer.spotify.com/documentation/web-api/concepts/authorization)
- [Frontend Testing Guide](./FRONTEND_TESTING_GUIDE.md)
- [Quick Start Guide](./QUICK_START.md)
