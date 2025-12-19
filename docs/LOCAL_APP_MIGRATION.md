# Converting to Local Single-User Application

## Summary

You're right that hosting user messages is a privacy concern. Converting to a local app makes sense. Here's what needs to change:

## Key Changes Required

### 1. Database Models ✅ (Started)
- **Created**: `local_models.py` - Simplified models (SpotifyToken, LocalCache)
- **Created**: `local_connection.py` - Simple local SQLite connection
- **Location**: Database stored at `~/.dopetracks/local.db`

### 2. Remove Authentication
- Remove all `get_current_user` dependencies
- Remove login/register endpoints
- Remove session management
- Remove user accounts

### 3. Simplify Endpoints
All endpoints that currently use `current_user: User = Depends(get_current_user)` need to:
- Remove the auth dependency
- Use `get_local_db_path()` instead of `get_user_db_path(user_data_service)`
- Use local Spotify token storage instead of per-user tokens

### 4. Frontend Changes
- Remove login/registration UI
- Skip authentication checks
- Simplify Spotify authorization flow

### 5. Spotify Token Management
- Store tokens in `SpotifyToken` table (no user_id foreign key)
- Single token set per installation

## Implementation Approach

### Option A: Create New Local App (Recommended)
Create `local_app.py` as a simplified version of `multiuser_app.py`:
- Copy core endpoints
- Remove all auth dependencies
- Simplify database access
- Use local helpers

### Option B: Add "Local Mode" Flag
Add a configuration flag to switch between multi-user and local mode:
- More complex but preserves both versions
- Conditional logic throughout

## Files Created So Far

1. ✅ `packages/dopetracks/local_models.py` - Simplified database models
2. ✅ `packages/dopetracks/local_connection.py` - Local database connection
3. ✅ `packages/dopetracks/local_helpers.py` - Helper functions
4. ✅ `start_local.py` - Startup script for local app
5. ✅ `docs/LOCAL_DEPLOYMENT.md` - Deployment guide

## Next Steps

1. **Create `local_app.py`** - Simplified FastAPI app without auth
2. **Update frontend** - Remove login UI, simplify flow
3. **Test locally** - Verify everything works
4. **Update README** - Add local deployment instructions

## Endpoints to Convert

Key endpoints that need changes:
- `/get-client-id` - Remove user session logic
- `/callback` - Store tokens in local table
- `/user-profile` - Get from local tokens
- `/user-playlists` - Get from local tokens
- `/chat-search-optimized` - Use `get_local_db_path()`
- `/create-playlist-optimized-stream` - Use local tokens and db path
- `/validate-username` - Simplify or remove
- `/validate-chat-file` - Simplify (no user association)

## Benefits of Local Deployment

✅ **Privacy**: All data stays on user's machine
✅ **Simplicity**: No user accounts or passwords
✅ **Security**: No server to secure
✅ **Easy Setup**: Just install and run
✅ **No Hosting Costs**: Runs locally

## Migration Path

For existing users:
1. Export Spotify tokens (if needed)
2. Run local version
3. Re-authorize Spotify (one-time)
4. Use Messages database directly from Mac

Would you like me to:
1. Create the full `local_app.py` with all endpoints converted?
2. Update the frontend to remove auth?
3. Both?
