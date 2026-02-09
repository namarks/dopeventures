# Troubleshooting

## 1. Server Won't Start / Connection Issues

### Port already in use

Another process is occupying port 8888.

```bash
lsof -i :8888
pkill -f uvicorn
```

Then restart the server.

### Virtual environment not active

If you see `ModuleNotFoundError` for `fastapi`, `sqlalchemy`, etc., the venv is not activated.

```bash
source dopetracks_env/bin/activate
# Prompt should show (dopetracks_env)
python3 -c "import fastapi; import sqlalchemy; print('OK')"
```

### Server starts but app can't connect

Verify the backend is actually listening:

```bash
curl http://127.0.0.1:8888/health
# Expected: {"status":"ok"}
```

If that works but the Swift app still fails, check Xcode console for connection errors and confirm `BackendManager` is pointed at `http://127.0.0.1:8888`.

---

## 2. Spotify Authorization Issues

### INVALID_CLIENT: Insecure redirect URI

Spotify rejects `localhost` in redirect URIs. You must use `127.0.0.1`.

The redirect URI must match exactly in two places:

| Location | Required value |
|---|---|
| `.env` file | `SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback` |
| Spotify Developer Dashboard > Redirect URIs | `http://127.0.0.1:8888/callback` |

Rules:
- Use `http://`, not `https://`, for loopback addresses.
- Use `127.0.0.1`, not `localhost`.
- No trailing slash.

After changing `.env`, restart the server.

### INVALID_CLIENT: Invalid redirect URI

The URI registered in the Spotify Dashboard does not match what the backend sends. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard), open your app settings, and confirm the redirect URI is `http://127.0.0.1:8888/callback`.

### Callback fails / no redirect after Spotify login

Check the server log for the actual redirect URI being used:

```bash
grep -i "redirect URI" backend.log | tail -5
```

If it shows `localhost`, your `.env` is wrong. See the table above.

Also verify `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env` match your Spotify Dashboard app.

### Token expired

Tokens auto-refresh. If you see "Spotify token expired -- please re-authorize" in the app, the refresh token itself has been revoked or the stored credentials are corrupt.

Fix: Re-authorize through the app. The backend exchanges a new token automatically on callback.

---

## 3. Messages Database Issues

### Database not found

The app reads `~/Library/Messages/chat.db`. If it can't find or open this file, the most likely cause is missing Full Disk Access.

Grant it: **System Settings > Privacy & Security > Full Disk Access** -- add your terminal app (Terminal.app, iTerm, or the Dopetracks app itself).

The backend also exposes a helper endpoint:

```bash
curl http://127.0.0.1:8888/open-full-disk-access
```

This opens System Settings directly to the Full Disk Access pane.

### "No Messages database found" error from the API

Returned when the server cannot stat `~/Library/Messages/chat.db`. Causes:

1. Full Disk Access not granted (most common).
2. Running under a different user account than the one that owns the Messages database.
3. iMessage has never been used on this Mac (the file does not exist).

---

## 4. Playlist Creation Issues

### No tracks found

"No Spotify track links found" means the selected chat(s) contained no Spotify track URLs (`open.spotify.com/track/...`).

Check:
- You selected the correct group chat.
- The chat actually contains Spotify links (not Apple Music, YouTube, etc.).
- The date range filter (if any) covers the period when links were shared.

"No messages found" means the chat selection returned zero messages entirely. Confirm the chat ID is valid and the prepared messages database has been built (the server does this on startup).

### All tracks skipped / duplicates

The app skips tracks already in the target playlist. If every track is marked "Already in playlist," the playlist is fully up to date. This is expected behavior on repeat runs.

If a track shows an error instead, check the server log for Spotify API errors (e.g., track removed from Spotify, regional restrictions).

---

## 5. Quick Diagnostic Commands

```bash
# Is the server running?
curl http://127.0.0.1:8888/health

# What is using port 8888?
lsof -i :8888

# Is the venv active?
echo $VIRTUAL_ENV && which python3

# Can Python import the dependencies?
python3 -c "import fastapi; import sqlalchemy; import spotipy; print('OK')"

# What redirect URI is configured?
grep SPOTIFY_REDIRECT_URI .env

# Can we access the Messages database?
ls -la ~/Library/Messages/chat.db

# Recent errors in the server log
grep ERROR backend.log | tail -20

# Spotify-related log entries
grep -i spotify backend.log | tail -20

# Follow the log in real time
tail -f backend.log
```
