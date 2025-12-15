# Testing via Swagger UI (/docs)

The Swagger UI at http://localhost:8888/docs is the easiest way to test your application. Here's how to test the complete workflow.

## Step-by-Step Testing Guide

### Step 1: Health Check ✅

1. Find **`GET /health`** in the Swagger UI
2. Click on it to expand
3. Click **"Try it out"**
4. Click **"Execute"**
5. **Expected:** Status 200 with `{"status": "healthy", "database": "connected"}`

---

### Step 2: Register a User

1. Find **`POST /auth/register`**
2. Click **"Try it out"**
3. Fill in the request body:
   ```json
   {
     "username": "testuser",
     "email": "test@example.com",
     "password": "TestPassword123!"
   }
   ```
4. Click **"Execute"**
5. **Expected:** Status 200 with user info and message "Registration successful"
6. **Important:** Copy the session cookie from the response headers (you'll need it)

**Note:** The response will include a `Set-Cookie` header. In a real browser, this would be set automatically. For Swagger testing, you may need to manually set cookies for subsequent requests.

---

### Step 3: Login

1. Find **`POST /auth/login`**
2. Click **"Try it out"**
3. Fill in:
   ```json
   {
     "username": "testuser",
     "password": "TestPassword123!"
   }
   ```
4. Click **"Execute"**
5. **Expected:** Status 200 with user info

---

### Step 4: Check Authentication Status

1. Find **`GET /auth/status`**
2. Click **"Try it out"**
3. Click **"Execute"**
4. **Expected:** 
   - If authenticated: `{"authenticated": true, "user": {...}}`
   - If not: `{"authenticated": false}`

**Note:** Swagger UI should automatically use cookies from previous requests. If you get "authenticated: false", you may need to manually set the cookie (see "Setting Cookies" section below).

---

### Step 5: Get Spotify Client ID

1. Find **`GET /get-client-id`**
2. Click **"Try it out"**
3. Click **"Execute"**
4. **Expected:** Status 200 with `{"client_id": "your_client_id"}`

This confirms your Spotify configuration is set up.

---

### Step 6: Validate Messages Database

You have two options:

#### Option A: Validate System Username

1. Find **`GET /validate-username`**
2. Click **"Try it out"**
3. Enter your macOS username in the `username` parameter
   - You can find it by running `whoami` in terminal
4. Click **"Execute"**
5. **Expected:** Status 200 confirming database path

#### Option B: Upload Database File

1. Find **`POST /validate-chat-file`**
2. Click **"Try it out"**
3. Click **"Choose File"** and select your `chat.db` file
   - Usually at: `~/Library/Messages/chat.db`
4. Click **"Execute"**
5. **Expected:** Status 200 with file validation info

---

### Step 7: Get Chat List (NEW - Optimized) ⚡

1. Find **`GET /chats`**
2. Click **"Try it out"**
3. Click **"Execute"**
4. **Expected:** Status 200 with array of chats
   ```json
   [
     {
       "chat_id": 16,
       "name": "Dopetracks",
       "chat_identifier": "iMessage;+;chat123456",
       "message_count": 1234,
       "spotify_message_count": 56,
       "recent_messages": [
         {
           "text": "Check out this song!",
           "is_from_me": false,
           "date": "2024-12-14 15:30:00"
         }
       ],
       ...
     }
   ]
   ```
   **Note:** If you see duplicate names, check `recent_messages` to identify which one you want, then use `chat_id` for selection.

**This should be FAST** (less than 1 second) - no upfront processing needed!

---

### Step 8: Search Chats (NEW - Optimized) ⚡

1. Find **`GET /chat-search-optimized`**
2. Click **"Try it out"**
3. Enter a search term in the `query` parameter (e.g., "dope")
4. Click **"Execute"**
5. **Expected:** Status 200 with matching chats
   ```json
   [
     {
       "chat_id": 16,
       "name": "Dopetracks",
       "chat_identifier": "iMessage;+;chat123456",
       "recent_messages": [...],
       "most_recent_song_date": "2024-12-14"
     }
   ]
   ```
   **Note:** All matching entries are shown (including duplicates). Use `recent_messages` to identify which one you want, then use `chat_id` for playlist creation.

---

### Step 9: Authorize Spotify (Browser Required)

**Note:** This requires a browser redirect, so it's easier to do manually:

1. Get your client ID from Step 5
2. Construct this URL:
   ```
   https://accounts.spotify.com/authorize?
     client_id=YOUR_CLIENT_ID&
     response_type=code&
     redirect_uri=http://localhost:8888/callback&
     scope=playlist-modify-public playlist-modify-private
   ```
3. Open in browser and authorize
4. You'll be redirected to `/callback` which stores tokens

**Verify tokens stored:**
1. Find **`GET /user-profile`**
2. Click **"Try it out"** → **"Execute"**
3. **Expected:** Your Spotify profile info

---

### Step 10: Create Playlist (NEW - Optimized) ⚡

1. Find **`POST /create-playlist-optimized`**
2. Click **"Try it out"**
3. Fill in the request body:
   ```json
   {
     "playlist_name": "Test Playlist",
     "start_date": "2024-01-01",
     "end_date": "2024-12-31",
     "selected_chat_ids": "[16]",
     "existing_playlist_id": null
   }
   ```
   **Important:** Use `selected_chat_ids` (array of integers) not `selected_chats` (names)
   - Get chat IDs from `/chats` or `/chat-search-optimized` responses
   - Use `chat_id` field from the search results
   - This avoids ambiguity with duplicate chat names
4. Click **"Execute"**
5. **Expected:** Status 200 with playlist info and tracks added

---

### Step 11: Get Summary Stats (NEW)

1. Find **`POST /summary-stats`**
2. Click **"Try it out"**
3. Fill in:
   ```json
   {
     "chat_ids": "[16]",
     "start_date": "2024-01-01",
     "end_date": "2024-12-31"
   }
   ```
   **Important:** Use `chat_ids` (array of integers) not `chat_names`
   - Get chat IDs from `/chats` or `/chat-search-optimized` responses
   - Use `chat_id` field from the search results
4. Click **"Execute"**
5. **Expected:** Status 200 with user statistics

---

## Setting Cookies in Swagger UI

If authentication isn't working automatically:

1. Look at the **"Authorize"** button at the top right of Swagger UI
2. Click it
3. You'll see options for authentication
4. For session-based auth, you may need to:
   - Copy the cookie from a previous response
   - Set it manually in your browser's developer tools
   - Or use the browser's network tab to see the Set-Cookie header

**Alternative:** Use curl or a tool like Postman that handles cookies automatically.

---

## Quick Test Checklist

Use this to verify everything works:

- [ ] Health check returns "healthy"
- [ ] Can register a new user
- [ ] Can login with registered user
- [ ] Can get Spotify client ID
- [ ] Can validate database (username or file upload)
- [ ] Can get chat list (fast!)
- [ ] Can search chats
- [ ] Can authorize Spotify (via browser)
- [ ] Can create playlist
- [ ] Can get summary stats

---

## Tips for Swagger UI

1. **Scroll through endpoints** - They're organized by tags (auth, default, etc.)
2. **Use "Try it out"** - This enables the interactive testing
3. **Check responses** - Look at both the response body and status code
4. **Read descriptions** - Each endpoint has documentation
5. **Check schemas** - Click "Schema" to see request/response formats

---

## Common Issues in Swagger

### "401 Unauthorized"
- You're not logged in
- Complete login step first
- Check that cookies are being sent

### "400 Bad Request"
- Check your request body format
- Make sure JSON strings are properly escaped
- Check parameter types (string vs array)

### "500 Internal Server Error"
- Check terminal for error messages
- Verify database is accessible
- Check environment variables are set

---

## Next Steps

Once you've tested via Swagger:
1. Test the frontend (if you have it set up)
2. Test with real data (your actual Messages database)
3. Test with multiple users
4. Test edge cases (empty chats, no Spotify links, etc.)

See `TESTING_GUIDE.md` for more comprehensive testing options.
