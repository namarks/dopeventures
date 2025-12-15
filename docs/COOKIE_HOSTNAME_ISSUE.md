# Cookie Hostname Issue: localhost vs 127.0.0.1

## The Problem

Browsers treat `localhost` and `127.0.0.1` as **different origins** for cookie purposes. This means:
- Cookies set when accessing `http://localhost:8888` don't work for `http://127.0.0.1:8888`
- Cookies set when accessing `http://127.0.0.1:8888` don't work for `http://localhost:8888`

## Why This Matters

Spotify requires `127.0.0.1` (not `localhost`) for redirect URIs in OAuth flows. So:
- You must use `127.0.0.1` for the Spotify callback
- But if you log in via `localhost`, your session cookie won't work when Spotify redirects to `127.0.0.1`

## The Solution

**Always use `127.0.0.1` consistently:**
- Access the app via: `http://127.0.0.1:8888`
- Login via: `http://127.0.0.1:8888`
- Spotify will redirect to: `http://127.0.0.1:8888/callback` (matches!)

## What We Changed

1. **Frontend config** (`website/config.js`):
   - Changed `BASE_URL` from `http://localhost:8888` to `http://127.0.0.1:8888`
   - This ensures all API calls use `127.0.0.1`

2. **Cookie settings**:
   - Cookies are set without a domain (hostname-specific)
   - This is correct - cookies work for the hostname you access

## Usage

**Always access the app via:**
```
http://127.0.0.1:8888
```

**NOT:**
```
http://localhost:8888  ❌ (cookies won't work with Spotify callback)
```

## Why Not Set Cookie Domain?

We can't set `domain=None` or omit domain to make cookies work for both, because:
- Cookies are inherently hostname-specific for security
- Setting a domain would make cookies less secure
- The solution is to use one hostname consistently

## Quick Fix

If you've already logged in via `localhost`:
1. Clear cookies for `localhost:8888`
2. Access the app via `http://127.0.0.1:8888`
3. Log in again
4. Now cookies will work with Spotify callback

## Verification

After logging in via `127.0.0.1:8888`:
1. Check browser DevTools (F12) → Application → Cookies
2. You should see `dopetracks_session` cookie
3. Domain should be `127.0.0.1` (or blank, which means current hostname)
4. When Spotify redirects to `127.0.0.1:8888/callback`, the cookie will be sent

## See Also

- [SPOTIFY_OAUTH_SETUP.md](./SPOTIFY_OAUTH_SETUP.md) - Why Spotify requires 127.0.0.1
- [FRONTEND_TESTING_GUIDE.md](./FRONTEND_TESTING_GUIDE.md) - Frontend testing
