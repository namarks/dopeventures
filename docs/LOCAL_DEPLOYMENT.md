# Local Deployment Guide

## Overview

This guide explains how to convert Dopetracks from a multi-user web application to a **local single-user application** that runs on each user's MacBook. This approach is better for privacy since user messages never leave their device.

## Why Local Deployment?

- **Privacy**: iMessage data stays on the user's machine
- **Simplicity**: No user accounts, passwords, or authentication
- **Security**: No server to secure or data to protect
- **Easy Setup**: Just install and run locally

## Architecture Changes

### Before (Multi-User)
- User authentication (login/register)
- User sessions and cookies
- Per-user data isolation
- Database stores user accounts
- Spotify tokens tied to user accounts

### After (Local)
- No authentication required
- Single user per installation
- Spotify tokens stored locally
- Simple local SQLite database
- All data stays on device

## Setup Instructions

### 1. Install Dependencies

```bash
cd dopeventures
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Spotify

Create a `.env` file:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

### 3. Run the Local App

```bash
python3 start_local.py
```

The app will be available at: http://127.0.0.1:8888

### 4. Grant Full Disk Access (macOS)

1. System Preferences → Security & Privacy → Privacy
2. Select "Full Disk Access"
3. Add Terminal (or your Python interpreter)

## Database Location

The local database is stored at:
```
~/.dopetracks/local.db
```

This contains:
- Spotify OAuth tokens
- Local cache (optional, for performance)

## Migration from Multi-User Version

If you have existing data in the multi-user version:

1. **Export Spotify Tokens**: Copy your Spotify tokens from the old database
2. **Import to Local**: The local app will prompt you to authorize Spotify on first run
3. **No Message Data Migration Needed**: Messages are read directly from your Mac's Messages database

## Differences from Multi-User Version

### Removed Features
- User registration/login
- User accounts
- Password management
- Admin features
- Multi-user data isolation

### Simplified Features
- Spotify authorization (no user association)
- Chat search (reads directly from Messages database)
- Playlist creation (uses local Spotify tokens)

### New Features
- Automatic Messages database detection
- Simpler setup flow
- No authentication required

## Troubleshooting

### "Database not found"
- Make sure you've granted Full Disk Access
- Or manually specify the path to `chat.db`

### "Spotify not authorized"
- Click "Authorize Spotify" in the UI
- Complete the OAuth flow
- Tokens are stored locally in `~/.dopetracks/local.db`

### Port Already in Use
```bash
lsof -ti:8888 | xargs kill -9
```

## Security Notes

- All data stays on your local machine
- Spotify tokens are stored in local SQLite database
- No network communication except Spotify API
- Messages database is read-only (never modified)

## Next Steps

After converting to local deployment:
1. Remove multi-user code (optional cleanup)
2. Update documentation
3. Consider packaging as a standalone app (PyInstaller, etc.)
