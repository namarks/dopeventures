# Frontend Testing Guide

## Quick Start

1. **Start the server:**
   ```bash
   python3 start.py
   ```

2. **Open your browser to:**
   ```
   http://localhost:8888/
   ```

3. **You should see** the Dopetracks web interface!

## What You'll See

The frontend is a multi-step workflow interface:

### Step 1: Spotify Authorization
- Connect your Spotify account
- Required for playlist creation

### Step 2: System Setup
- Upload or validate your Messages database (`chat.db`)
- Required for accessing your chat data

### Step 3: Data Preparation
- Process your iMessage data
- Takes ~45 seconds
- Only needed for old endpoints (optimized endpoints skip this!)

### Step 4: Chat Search & Selection
- Search for chats by name
- **Select multiple chats** using checkboxes
- See chat details: members, message counts, Spotify URLs
- View recent messages to identify duplicate chat entries

### Step 5: Playlist Creation
- Enter playlist name
- Set date range
- Create playlist from selected chats

## Testing the Complete Workflow

### 1. Register/Login

**First time:**
- Click "Register" or "Sign Up"
- Enter username, email, password
- Click "Register"

**Returning user:**
- Enter username and password
- Click "Login"

### 2. Authorize Spotify

1. Click "Authorize Spotify" button
2. You'll be redirected to Spotify
3. Log in and grant permissions
4. You'll be redirected back
5. Status should show "✅ Spotify authorized"

### 3. System Setup

**Option A: Upload Database**
1. Click "Choose File"
2. Select your `chat.db` file (usually at `~/Library/Messages/chat.db`)
3. Click "Upload and Validate"
4. Wait for validation

**Option B: Validate Existing Path**
1. Enter your macOS username
2. Click "Validate Username"
3. System will check for database at default location

### 4. Chat Search (NEW - Optimized!)

**Note:** With the optimized endpoints, you can skip data preparation!

1. Enter a search term (e.g., "dope", "music", etc.)
2. Click "Search Chats"
3. Results appear in a table with:
   - Checkbox to select chats
   - Chat name
   - Chat ID (important for duplicates!)
   - Member count
   - Total messages
   - Your messages
   - Spotify URLs count
   - Most recent song date
   - Recent messages (hover over date to see)

4. **Select multiple chats:**
   - Check the boxes next to chats you want
   - You can select multiple chats with the same name!
   - Selected chats appear below the table
   - Counter shows how many you've selected

### 5. Create Playlist

1. Enter playlist name
2. Set start date (e.g., "2024-01-01")
3. Set end date (e.g., "2024-12-31")
4. Click "Create Playlist"
5. Wait for processing (shows progress)
6. Success message appears with track count

## Testing Multi-Chat Selection

This is the new feature! Here's how to test it:

### Scenario: Duplicate Chat Names

1. **Search for a chat** that might have duplicates (e.g., "dopetracks")

2. **Look for multiple entries** with the same name but different Chat IDs

3. **Check the recent messages** (hover over "Most Recent Song Date"):
   - Chat 4198: Messages from Jan-Oct 2025
   - Chat 4387: Messages from Oct-Dec 2025

4. **Select both chats:**
   - Check box for Chat 4198
   - Check box for Chat 4387
   - Both should appear in "Selected Chats" section

5. **Create playlist:**
   - Enter playlist name
   - Set date range covering both periods
   - Click "Create Playlist"
   - Should combine tracks from both chats!

## Troubleshooting

### Frontend Not Loading

**Check server logs:**
```bash
# Look for this message:
INFO: Serving static files from website directory
```

**If you see:**
```
WARNING: Website directory not found - static files not served
```

**Fix:**
- Make sure `website/` folder exists in project root
- Check that `index.html` is in `website/` folder

### Authentication Issues

**Problem:** Can't log in or register

**Check:**
1. Open browser console (F12)
2. Look for errors in Console tab
3. Check Network tab for failed requests

**Common issues:**
- Backend not running
- Database not initialized
- CORS errors (shouldn't happen, but check)

### Chat Search Not Working

**Problem:** Search returns no results or errors

**Check:**
1. Make sure you've completed System Setup
2. Verify database path is correct
3. Check browser console for errors
4. Try the optimized endpoint directly: `/chat-search-optimized?query=test`

### Playlist Creation Fails

**Problem:** Error creating playlist

**Check:**
1. Spotify authorized? (Step 1)
2. At least one chat selected?
3. Date range valid?
4. Browser console for error details

**Common errors:**
- "No Spotify authorization" → Complete Step 1
- "No chats selected" → Select at least one chat
- "No messages found" → Adjust date range or select different chats

## Browser Developer Tools

### Opening DevTools

- **Chrome/Edge:** F12 or Right-click → Inspect
- **Firefox:** F12 or Right-click → Inspect Element
- **Safari:** Cmd+Option+I (enable Developer menu first)

### Useful Tabs

1. **Console:**
   - See JavaScript errors
   - See API responses
   - Debug messages

2. **Network:**
   - See all API requests
   - Check request/response data
   - Verify endpoints are being called

3. **Application/Storage:**
   - See stored authentication tokens
   - Check cookies
   - View local storage

## Testing Tips

### 1. Test with Real Data

Use your actual `chat.db` file for realistic testing:
- Real chat names
- Real message counts
- Real Spotify links

### 2. Test Edge Cases

- **No results:** Search for something that doesn't exist
- **Many results:** Search for common terms
- **Duplicate names:** Search for chats you know have duplicates
- **Empty selection:** Try creating playlist with no chats selected
- **Invalid dates:** Try invalid date ranges

### 3. Test Multi-Select

- Select 1 chat → Create playlist
- Select 2 chats → Create playlist
- Select 3+ chats → Create playlist
- Select, deselect, reselect → Verify state

### 4. Test Responsiveness

- Resize browser window
- Test on mobile device (if accessible)
- Check table scrolling on small screens

## Expected Behavior

### Chat Search Results

- **Table appears** with results
- **Header note** about multi-select capability
- **Checkboxes** are clickable
- **Recent messages** visible on hover
- **Chat IDs** displayed for identification

### Selected Chats Display

- **Counter** shows number selected
- **Badges** show chat name and ID
- **Remove buttons** (×) work
- **Clear All** button appears when chats selected

### Playlist Creation

- **Button enabled** when:
  - Spotify authorized ✓
  - System setup complete ✓
  - At least one chat selected ✓
- **Progress indicator** during creation
- **Success message** with track count
- **Option to clear** selected chats after success

## Quick Test Checklist

- [ ] Server starts without errors
- [ ] Frontend loads at `http://localhost:8888/`
- [ ] Can register new user
- [ ] Can login with existing user
- [ ] Can authorize Spotify
- [ ] Can upload/validate database
- [ ] Can search for chats
- [ ] Can select multiple chats
- [ ] Can see selected chats counter
- [ ] Can create playlist
- [ ] Playlist creation succeeds
- [ ] Can see success message

## Comparison: Frontend vs Swagger

| Feature | Frontend | Swagger (/docs) |
|---------|----------|-----------------|
| **User-friendly** | ✅ Yes | ❌ Technical |
| **Multi-select** | ✅ Checkboxes | ❌ Manual JSON |
| **Visual feedback** | ✅ Progress bars | ❌ Text only |
| **Error handling** | ✅ User-friendly | ❌ Technical errors |
| **Workflow** | ✅ Step-by-step | ❌ Manual steps |
| **Testing speed** | ⚠️ Slower (UI) | ✅ Fast (direct API) |
| **Debugging** | ⚠️ Harder | ✅ Easy (see requests) |

**Recommendation:** Use frontend for normal testing, Swagger for debugging API issues.

## Next Steps

After testing the frontend:
1. Try creating a real playlist with your data
2. Test with multiple chats selected
3. Verify tracks appear in your Spotify account
4. Check that duplicate chat names work correctly

## See Also

- [BROWSER_ACCESS.md](./BROWSER_ACCESS.md) - Basic browser access info
- [TESTING_VIA_SWAGGER.md](./TESTING_VIA_SWAGGER.md) - API endpoint testing
- [MULTI_CHAT_PLAYLISTS.md](./MULTI_CHAT_PLAYLISTS.md) - Multi-chat feature guide
