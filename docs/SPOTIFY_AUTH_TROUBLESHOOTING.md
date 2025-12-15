# Spotify Authorization Troubleshooting

## Quick Diagnosis

**What error are you seeing?** This will help identify the issue:

1. **"INVALID_CLIENT: Insecure redirect URI"**
   → See [Redirect URI Issues](#redirect-uri-issues)

2. **"401 Unauthorized" when redirected back**
   → See [Authentication Issues](#authentication-issues)

3. **"Authorization code not provided"**
   → See [Callback Issues](#callback-issues)

4. **Redirects but status doesn't update**
   → See [Status Update Issues](#status-update-issues)

5. **Nothing happens when clicking "Authorize Spotify"**
   → See [Button Not Working](#button-not-working)

---

## Redirect URI Issues

### Error: "INVALID_CLIENT: Insecure redirect URI"

**Cause:** The redirect URI in your code doesn't match what's registered in Spotify Dashboard.

**Fix:**
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click your app → "Edit Settings"
3. Under "Redirect URIs", add exactly:
   ```
   http://localhost:8888/callback
   ```
4. Click "Add" then "Save"
5. Verify your `.env` file has:
   ```
   SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
   ```
6. Restart server

**Check:**
- No trailing slash
- Uses `http://` for localhost (not `https://`)
- Exact match with Dashboard

---

## Authentication Issues

### Error: "401 Unauthorized" on `/callback`

**Cause:** The `/callback` endpoint requires you to be logged in, but your session might have expired or not be set.

**Fix:**
1. **Make sure you're logged in first:**
   - Go to `http://localhost:8888/`
   - Register or login
   - **Then** click "Authorize Spotify"

2. **Check session cookie:**
   - Open browser DevTools (F12)
   - Go to Application/Storage → Cookies
   - Look for `dopetracks_session` cookie
   - If missing, you're not logged in

3. **Try in same browser session:**
   - Don't close browser between login and Spotify auth
   - Don't use incognito mode (cookies might not persist)

**Workaround:** If this keeps happening, we can make the callback endpoint handle unauthenticated users by storing the code temporarily.

---

## Callback Issues

### Error: "Authorization code not provided"

**Cause:** Spotify didn't send the authorization code in the callback.

**Possible reasons:**
1. User denied authorization on Spotify page
2. Redirect URI mismatch
3. Authorization code expired (codes expire quickly)

**Fix:**
1. Try authorizing again immediately
2. Make sure you click "Agree" on Spotify's authorization page
3. Check browser console for redirect URI being sent
4. Verify redirect URI in Spotify Dashboard matches exactly

---

## Status Update Issues

### Problem: Authorization succeeds but UI doesn't update

**Cause:** Frontend not checking status after redirect.

**Fix:**
1. **Manual refresh:**
   - After seeing "Spotify Authorization Successful" page
   - Wait for redirect to main app
   - Refresh the page (F5)
   - Status should update

2. **Check browser console:**
   - Open DevTools (F12)
   - Look for errors
   - Check if `/user-profile` is being called

3. **Verify tokens stored:**
   - Check server logs for: "Spotify tokens stored for user..."
   - If you see this, tokens are saved
   - Just need to refresh UI

**Recent fix:** The frontend now automatically checks status after callback redirect.

---

## Button Not Working

### Problem: Clicking "Authorize Spotify" does nothing

**Check:**
1. **Browser console (F12):**
   - Look for JavaScript errors
   - Check if button click is registered

2. **Network tab:**
   - See if `/get-client-id` is called
   - Check response

3. **Server logs:**
   - See if `/get-client-id` endpoint is hit
   - Check for errors

**Common causes:**
- JavaScript error preventing execution
- CORS issues (shouldn't happen on same origin)
- Server not running

---

## Step-by-Step Debugging

### 1. Check Configuration
```bash
python3 scripts/debug/debug_spotify_oauth.py
```
This will verify your `.env` settings.

### 2. Test Authorization URL
```bash
python3 scripts/debug/test_spotify_flow.py
```
This shows the exact URL that should be used.

### 3. Check Browser Console
1. Open DevTools (F12)
2. Go to Console tab
3. Click "Authorize Spotify"
4. Look for:
   - "Using redirect URI: ..."
   - "Redirecting to: ..."
   - Any errors

### 4. Check Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Click "Authorize Spotify"
4. Look for:
   - Request to `/get-client-id`
   - Redirect to Spotify
   - Callback to `/callback`
   - Check status codes (should be 200)

### 5. Check Server Logs
Look for:
- "Spotify token exchange failed" → Redirect URI mismatch
- "Spotify tokens stored" → Success!
- "401 Unauthorized" → Not logged in
- "Authorization code not provided" → Code missing

---

## Common Workflows

### First Time Setup
1. ✅ Register/Login to app
2. ✅ Click "Authorize Spotify"
3. ✅ Redirected to Spotify
4. ✅ Click "Agree"
5. ✅ Redirected back to app
6. ✅ See "Spotify Authorization Successful"
7. ✅ Auto-redirect to main app
8. ✅ Status shows "Connected to Spotify"

### If Step 3 Fails
→ Redirect URI not in Spotify Dashboard

### If Step 5 Fails
→ Not logged in, or session expired

### If Step 8 Doesn't Update
→ Refresh page, or check browser console

---

## Still Not Working?

1. **Share the exact error message** from:
   - Browser console
   - Server logs
   - Error page

2. **Describe what happens:**
   - Does it redirect to Spotify? ✓/✗
   - Do you see authorization page? ✓/✗
   - After clicking "Agree", what happens?
   - What page do you end up on?

3. **Check these:**
   - Are you logged into the app?
   - Is redirect URI in Spotify Dashboard?
   - Did you restart server after changing `.env`?
   - Are you using the correct Spotify app (check Client ID)?

---

## Quick Fixes

### Fix 1: Clear Everything and Start Fresh
```bash
# 1. Clear browser cookies for localhost
# 2. Restart server
python3 start_multiuser.py

# 3. Register/login again
# 4. Try Spotify auth again
```

### Fix 2: Verify Spotify Dashboard
1. Go to https://developer.spotify.com/dashboard
2. Click your app
3. Click "Edit Settings"
4. Verify Redirect URIs includes: `http://localhost:8888/callback`
5. Click "Save"

### Fix 3: Check .env File
```bash
# Should have:
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

---

## See Also

- [SPOTIFY_OAUTH_SETUP.md](./SPOTIFY_OAUTH_SETUP.md) - Initial setup guide
- [FRONTEND_TESTING_GUIDE.md](./FRONTEND_TESTING_GUIDE.md) - Frontend testing
- [QUICK_START.md](./QUICK_START.md) - Getting started
