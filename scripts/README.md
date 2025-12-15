# Scripts Directory

This directory contains debugging and utility scripts for the Dopetracks project.

## Structure

### `debug/`
Debugging and testing scripts for troubleshooting various components:

- **Chat debugging:**
  - `check_chat_service.py` - Check service types of messages in a chat
  - `compare_chat_members.py` - Compare members between two chats
  - `compare_chats.py` - Compare two chat entries by chat_id
  - `debug_chat_duplicates.py` - Investigate duplicate chat names in Messages database

- **Spotify OAuth debugging:**
  - `debug_spotify_auth.py` - Basic Spotify OAuth configuration check
  - `debug_spotify_oauth.py` - Comprehensive Spotify OAuth debugging
  - `verify_spotify_redirect.py` - Verify Spotify redirect URI configuration
  - `verify_spotify_setup.py` - Final verification for Spotify OAuth setup
  - `test_spotify_flow.py` - Test Spotify OAuth flow

- **General testing:**
  - `test_workflow.py` - Test main application endpoints and workflow

### `utils/`
Utility scripts for common tasks:

**Shell scripts:**
- `fix_spotify_redirect.sh` - Update SPOTIFY_REDIRECT_URI in .env file
- `force_restart_server.sh` - Force restart server with new environment variables
- `kill_server.sh` - Kill any running Dopetracks server processes
- `setup_and_run.sh` - Quick setup and run script (activates venv and starts server)

**Database migrations:**
- `migrate_password_reset.py` - Add password reset table to existing database
- `migrate_roles.py` - Add role and permissions columns to users table

**Admin utilities:**
- `promote_admin.py` - Promote users to admin or super_admin roles
- `reset_password.py` - Reset a user's password to a known value

## Usage

All scripts can be run from the project root directory. For example:

```bash
# Debug scripts
python3 scripts/debug/check_chat_service.py <chat_id>
python3 scripts/debug/debug_spotify_oauth.py

# Utility scripts
./scripts/utils/kill_server.sh
./scripts/utils/setup_and_run.sh
```

Make sure scripts have execute permissions for shell scripts:
```bash
chmod +x scripts/utils/*.sh
```
