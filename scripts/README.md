# Scripts Directory

Debugging and utility scripts for the Dopetracks project.

## `debug/`

**Chat debugging:**
- `check_chat_service.py` - Check service types of messages in a chat
- `compare_chat_members.py` - Compare members between two chats
- `compare_chats.py` - Compare two chat entries by chat_id
- `debug_chat_duplicates.py` - Investigate duplicate chat names in Messages database

**Spotify OAuth debugging:**
- `debug_spotify_auth.py` - Basic Spotify OAuth configuration check
- `debug_spotify_oauth.py` - Comprehensive Spotify OAuth debugging
- `verify_spotify_redirect.py` - Verify Spotify redirect URI configuration
- `verify_spotify_setup.py` - Final verification for Spotify OAuth setup
- `test_spotify_flow.py` - Test Spotify OAuth flow

**General testing:**
- `test_workflow.py` - Test main application endpoints and workflow

## `utils/`

Shell scripts for common operations:
- `fix_spotify_redirect.sh` - Update SPOTIFY_REDIRECT_URI in .env file
- `force_restart_server.sh` - Force restart server with new environment variables
- `kill_server.sh` - Kill any running Dopetracks server processes
- `setup_and_run.sh` - Quick setup and run script (activates venv and starts server)

## Usage

Run scripts from the project root:

```bash
python3 scripts/debug/check_chat_service.py <chat_id>
python3 scripts/debug/debug_spotify_oauth.py
./scripts/utils/kill_server.sh
```
