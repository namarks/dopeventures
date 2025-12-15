# How to Check Server Logs

## Where to Find Logs

### 1. Terminal Output (Primary)

The server logs appear **directly in the terminal** where you started the server.

**To see logs:**
1. Find the terminal window where you ran `python3 start_multiuser.py`
2. Look at the output - logs appear in real-time as things happen
3. Scroll up to see older logs

**What you'll see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8888
INFO:     Application startup complete
INFO:     127.0.0.1:49624 - "POST /auth/login HTTP/1.1" 200 OK
2025-12-14 14:43:48 - dopetracks.multiuser_app - INFO - OAuth request - Client ID: ff64133e29..., Redirect URI: http://127.0.0.1:8888/callback
```

### 2. Log File (If Enabled)

The server also writes to a log file: `backend.log` in the project root.

**To view log file:**
```bash
# View entire log file
cat backend.log

# View last 50 lines
tail -n 50 backend.log

# Follow log file in real-time (like `tail -f`)
tail -f backend.log
```

**Location:**
```
/Users/nmarks/root_code_repo/dopeventures/backend.log
```

## What to Look For

### When Testing Spotify Authorization

**Look for these log messages:**

1. **When you click "Authorize Spotify":**
   ```
   OAuth request - Client ID: ff64133e29..., Redirect URI: http://127.0.0.1:8888/callback
   ```
   ✅ Should show `127.0.0.1` (NOT `localhost`)

2. **When Spotify redirects back:**
   ```
   Exchanging Spotify authorization code for tokens
   Using redirect URI: http://127.0.0.1:8888/callback
   ```
   ✅ Should show `127.0.0.1`

3. **If successful:**
   ```
   Spotify tokens stored for user testuser_1
   ```
   ✅ This means it worked!

4. **If it fails:**
   ```
   Spotify token exchange failed (status 400): {"error":"invalid_client","error_description":"Invalid redirect URI"}
   ```
   ❌ This means redirect URI mismatch

### Common Log Patterns

**Login:**
```
INFO:     127.0.0.1:49624 - "POST /auth/login HTTP/1.1" 200 OK
```

**Spotify OAuth:**
```
INFO:     127.0.0.1:49626 - "GET /get-client-id HTTP/1.1" 200 OK
OAuth request - Client ID: ..., Redirect URI: ...
```

**Errors:**
```
ERROR - Spotify token exchange failed: ...
WARNING - Could not get user from session: ...
```

## Tips for Reading Logs

### 1. Filter Logs

**In terminal (while server is running):**
- You can't easily filter, but you can scroll up
- Look for lines with "ERROR", "WARNING", or "INFO"

**In log file:**
```bash
# Show only errors
grep ERROR backend.log

# Show only Spotify-related logs
grep -i spotify backend.log

# Show last 20 lines with "redirect"
tail -n 100 backend.log | grep -i redirect
```

### 2. Real-Time Monitoring

**Watch logs as they happen:**
```bash
# In a separate terminal, run:
tail -f backend.log
```

This will show new log entries in real-time as you use the app.

### 3. Clear Old Logs

**If log file gets too large:**
```bash
# Clear the log file
> backend.log

# Or delete it (will be recreated)
rm backend.log
```

## Log Levels

The server uses different log levels:

- **INFO**: Normal operations (requests, successful operations)
- **WARNING**: Something unusual but not critical
- **ERROR**: Something went wrong
- **DEBUG**: Detailed debugging info (usually not shown)

## Example: Debugging Spotify Authorization

**Step 1: Start monitoring logs**
```bash
# In a separate terminal
tail -f backend.log
```

**Step 2: Try to authorize**
- Go to app
- Click "Authorize Spotify"

**Step 3: Watch for these messages:**

✅ **Good:**
```
INFO - OAuth request - Client ID: ff64133e29..., Redirect URI: http://127.0.0.1:8888/callback
INFO - Exchanging Spotify authorization code for tokens
INFO - Using redirect URI: http://127.0.0.1:8888/callback
INFO - Spotify tokens stored for user testuser_1
```

❌ **Bad:**
```
INFO - OAuth request - ... Redirect URI: http://localhost:8888/callback
ERROR - Spotify token exchange failed: Invalid redirect URI
```

## Quick Commands

```bash
# View last 50 lines
tail -n 50 backend.log

# View only errors
grep ERROR backend.log

# View Spotify-related logs
grep -i spotify backend.log | tail -n 20

# Follow logs in real-time
tail -f backend.log

# Count errors
grep -c ERROR backend.log
```

## If You Don't See Logs

1. **Check if server is running:**
   ```bash
   ps aux | grep uvicorn
   ```

2. **Check if log file exists:**
   ```bash
   ls -la backend.log
   ```

3. **Check terminal where server is running:**
   - Logs should appear there automatically
   - If not, server might have crashed

## See Also

- [SPOTIFY_OAUTH_SETUP.md](./SPOTIFY_OAUTH_SETUP.md) - Spotify setup guide
- [SPOTIFY_AUTH_TROUBLESHOOTING.md](./SPOTIFY_AUTH_TROUBLESHOOTING.md) - Troubleshooting guide
