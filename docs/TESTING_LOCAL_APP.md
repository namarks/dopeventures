# Testing the App

## Quick Start

1. **Start the app**:
   ```bash
   python3 start.py
   ```

2. **Open in browser**:
   - http://127.0.0.1:8888

3. **What to expect**:
   - No login required!
   - App should load directly
   - You'll need to authorize Spotify (one-time)
   - Then you can search chats and create playlists

## Features

- **No Authentication**: App loads immediately
- **Spotify OAuth**: Works without user accounts
- **Chat Search**: Uses local Messages database
- **Playlist Creation**: Full streaming with progress
- **Contact Photos**: Loads from AddressBook
- **Local Database**: Stored at `~/.dopetracks/local.db`
- **Messages DB**: Auto-detected from `~/Library/Messages/chat.db`

## Testing Checklist

### 1. Health Check
```bash
curl http://127.0.0.1:8888/health
```
Should return:
- `status: "healthy"`
- `messages_db: "found"` (if Full Disk Access granted)
- `messages_db_path: "/Users/.../Library/Messages/chat.db"`

### 2. Spotify Authorization
- Click "Authorize Spotify" button
- Complete OAuth flow
- Should redirect back and show success
- Check that `/user-profile` works

### 3. Chat Search
- Search for a chat name
- Should return results without errors
- Click "View Details" to see recent messages

### 4. Playlist Creation
- Select chats and date range
- Click "Create Playlist"
- Watch progress bar
- Should create playlist successfully

## Troubleshooting

### "No Messages database found"
- Grant Full Disk Access to Terminal/Python
- Or manually specify path (future feature)

### "Spotify not authorized"
- Click "Authorize Spotify" button
- Complete OAuth flow
- Tokens stored in `~/.dopetracks/local.db`

### Port Already in Use
```bash
lsof -ti:8888 | xargs kill -9
```

## Database Location

Local database: `~/.dopetracks/local.db`

Contains:
- `spotify_tokens` table (access_token, refresh_token, expires_at)
- `local_cache` table (optional, for caching)

## Next Steps

If testing goes well:
1. Update frontend to skip auth checks
2. Remove login UI completely
3. Simplify the flow
4. Update documentation
