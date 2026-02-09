# Dopetracks User Guide

From download to your first playlist.

## System Requirements

- macOS
- Spotify account
- Internet connection (for Spotify API)

## Setup

### 1. Install the App

Download `Dopetracks.dmg` from [GitHub Releases](https://github.com/namarks/dopeventures/releases/latest), open it, and drag `Dopetracks.app` to Applications.

### 2. Get Spotify Credentials

You need a free Spotify Developer App:

1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Sign in and click **Create App**
3. Fill in:
   - **App Name**: Dopetracks
   - **App Description**: Personal playlist creator
   - **Redirect URI**: `http://127.0.0.1:8888/callback` (use `127.0.0.1`, not `localhost`)
4. Save, then copy your **Client ID** and **Client Secret**

### 3. Grant macOS Permissions

The app needs Full Disk Access to read your Messages database:

1. Open **System Settings > Privacy & Security > Full Disk Access**
2. Click the lock icon and authenticate
3. Add the Dopetracks app (or Terminal if running from source)

### 4. First Launch

1. Open Dopetracks from Applications
2. The setup wizard will ask for your Spotify Client ID and Secret
3. Click **Connect to Spotify** and authorize in your browser

## Using the App

### Search Chats

Use the search bar to find chats by name or participant. Select one or more chats to include.

If you see duplicate chat names, these are separate conversation threads in the Messages database. Check message counts and dates to pick the right one. See [docs/CHAT_SELECTION_GUIDE.md](docs/CHAT_SELECTION_GUIDE.md) for details.

### Create a Playlist

1. Select chats to include
2. Optionally set a date range to filter messages
3. Enter a playlist name
4. Click **Create Playlist** and watch the progress
5. Open the link to view your playlist on Spotify

## Troubleshooting

**Server won't start**: Port 8888 may be in use. Kill it: `pkill -f uvicorn`

**Permission denied for Messages**: Grant Full Disk Access (see step 3 above).

**Spotify authorization fails**: Make sure your redirect URI is exactly `http://127.0.0.1:8888/callback` (not `localhost`).

For more help, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Security & Privacy

- All data stays on your Mac -- nothing is uploaded
- Your Messages database is read-only
- Spotify tokens are stored locally in `~/.dopetracks/local.db`
- No analytics, no telemetry
- Keep your `.env` file private -- it contains your Spotify credentials
