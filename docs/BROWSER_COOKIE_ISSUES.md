# Browser Cookie Issues: Cursor vs External Browser

## The Problem

Login works in Cursor's built-in browser but not in external browsers (Chrome, Firefox, Safari, etc.).

## Common Causes

### 1. CORS Configuration

**Issue:** External browsers enforce CORS more strictly than embedded browsers.

**Fix:** Make sure `http://127.0.0.1:8888` is in CORS_ORIGINS (already fixed).

### 2. Cookie Settings

**Issue:** Cookies might not be sent/received properly.

**Check:**
- Browser DevTools (F12) → Application → Cookies
- Look for `dopetracks_session` cookie
- Domain should be `127.0.0.1` (or blank)
- HttpOnly should be checked
- SameSite should be "Lax"

### 3. Credentials Not Included

**Issue:** Fetch requests might not include credentials.

**Fix:** All `apiFetch` calls now include `credentials: 'include'` automatically.

### 4. Browser Privacy Settings

**Issue:** Some browsers block third-party cookies or have strict privacy settings.

**Check:**
- Chrome: Settings → Privacy and security → Cookies
- Firefox: Settings → Privacy & Security → Cookies
- Safari: Preferences → Privacy → Cookies

**Temporary fix:** Allow all cookies for `127.0.0.1` in browser settings.

### 5. Incognito/Private Mode

**Issue:** Private browsing modes often block cookies more aggressively.

**Fix:** Try in normal (non-private) browsing mode.

## Debugging Steps

### 1. Check Browser Console

Open DevTools (F12) → Console:
- Look for CORS errors
- Look for cookie-related errors
- Check for network errors

### 2. Check Network Tab

Open DevTools (F12) → Network:
- Click "Login"
- Find the `/auth/login` request
- Check:
  - Status code (should be 200)
  - Request Headers (should include cookies if logged in)
  - Response Headers (should include `Set-Cookie`)
  - Response body (should have user data)

### 3. Check Cookies

Open DevTools (F12) → Application → Cookies:
- After login, you should see `dopetracks_session`
- If missing, cookies aren't being set
- If present but login still fails, cookies aren't being sent

### 4. Check CORS Headers

In Network tab, check response headers for:
- `Access-Control-Allow-Origin: http://127.0.0.1:8888`
- `Access-Control-Allow-Credentials: true`

If these are missing or wrong, CORS is blocking.

## Quick Fixes

### Fix 1: Clear Everything

1. Clear browser cache and cookies for `127.0.0.1:8888`
2. Close and reopen browser
3. Try again

### Fix 2: Check Browser Settings

**Chrome:**
- Settings → Privacy → Cookies
- Make sure "Block third-party cookies" isn't blocking `127.0.0.1`

**Firefox:**
- Settings → Privacy → Cookies
- Try "Standard" or "Custom" (allow all cookies)

**Safari:**
- Preferences → Privacy
- Uncheck "Prevent cross-site tracking" (temporarily for testing)

### Fix 3: Try Different Browser

If one browser doesn't work, try:
- Chrome
- Firefox
- Safari
- Edge

This helps identify if it's browser-specific.

### Fix 4: Check Server Logs

Look for:
- CORS errors
- Cookie setting errors
- Authentication errors

## What We Fixed

1. ✅ Added `127.0.0.1:8888` to CORS_ORIGINS
2. ✅ Updated `apiFetch` to always include `credentials: 'include'`
3. ✅ Set cookie `path="/"` to make it available everywhere
4. ✅ Updated frontend to use `127.0.0.1` consistently

## Still Not Working?

1. **Check browser console** for specific errors
2. **Check network tab** to see what's being sent/received
3. **Try a different browser** to isolate the issue
4. **Check browser privacy settings** - they might be too strict
5. **Try disabling browser extensions** - ad blockers can interfere

## Expected Behavior

After login:
1. Network tab shows `200 OK` for `/auth/login`
2. Response headers include `Set-Cookie: dopetracks_session=...`
3. Application → Cookies shows `dopetracks_session` cookie
4. Subsequent requests include `Cookie: dopetracks_session=...` header
5. `/auth/status` returns `{"authenticated": true}`

If any of these fail, that's where the issue is.
