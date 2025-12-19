# Dopetracks

Create Spotify playlists from songs shared in your iMessage chats.

## 🚀 Quick Start

**New to Dopetracks?** Start here: **[QUICK_START.md](./QUICK_START.md)** - Get running in 5 minutes!

### 🎯 No-Code Option (Easiest!)

**Don't want to use the command line?** Use the GUI Launcher:
1. Clone the repo: `git clone https://github.com/namarks/dopeventures.git`
2. Double-click `launch.py` 
3. Click "Setup (First Time)" then "Launch App"
4. That's it! See [README_LAUNCHER.md](./README_LAUNCHER.md) for details.

### Command Line Option

Or use the automated setup script:
```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures
./setup.sh
```

## What is Dopetracks?

Dopetracks automatically creates Spotify playlists from songs your friends have shared in iMessage chats. It:
1. Extracts messages from your Messages database (`~/Library/Messages/chat.db`)
2. Finds messages containing Spotify links
3. Creates a Spotify playlist with all the identified songs

## Prerequisites

- **macOS** (required for Messages database access)
- **Python 3.11+**
- **Spotify Premium account** (required for playlist creation)
- **Spotify Developer App** (free, 2-minute setup)

## Manual Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Tip**: Use `./setup.sh` to automate this step!

### 2. Spotify API Setup

1. **Create Spotify Developer App**:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Click "Create App"
   - App Name: "Dopetracks" (or any name)
   - App Description: "Personal playlist creator"
   - Redirect URI: `http://127.0.0.1:8888/callback` (⚠️ use 127.0.0.1, not localhost)
   - Check the boxes for Terms of Service
   - Click "Save"

2. **Get Your Credentials**:
   - Copy your **Client ID** and **Client Secret**

3. **Create Environment File**:
   The setup script creates a `.env` template, or create it manually:
   ```bash
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
   ```
   
   > **Note**: The setup script (`./setup.sh`) creates this file automatically.

### 3. Grant System Permissions (macOS)

**Enable Full Disk Access for Terminal/Python**:
1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Full Disk Access** from the left sidebar
3. Click the lock icon and enter your password
4. Click the "+" button and add:
   - **Terminal** (if running from Terminal)
   - **Python** (if you have a separate Python.app)
   - Or the specific application you're using

### 4. Configure Frontend

The setup script creates `website/config.js` automatically. If you need to create it manually:
```bash
echo 'const BASE_URL = "http://127.0.0.1:8888";' > website/config.js
```

### 5. Alternative: Upload Database File

If you prefer not to grant full disk access, you can:
1. Manually copy your Messages database: 
   ```bash
   cp ~/Library/Messages/chat.db ./my_messages.db
   ```
2. Use the file upload feature in the web interface

## Running the App

1. **Activate virtual environment** (if not already active):
   ```bash
   source venv/bin/activate
   ```

2. **Start the app**:
   ```bash
   python3 start.py
   ```

3. **Open your browser**:
   - Go to: **http://127.0.0.1:8888**
   - The app serves both frontend and backend from the same port

4. **Follow the steps**:
   1. **Authorize Spotify** - Click "Connect to Spotify" and complete OAuth
   2. **Verify System Access** - App will auto-detect your Messages database
   3. **Search Chats** - Search for chat names or participant names
   4. **Select Chats** - Choose which chats to include
   5. **Create Playlist** - Select date range and create your playlist!

## Troubleshooting

### Common Issues:

1. **"No module named 'packages'" Error**:
   - Make sure you're running the command from the project root (`dopeventures/`)
   - Ensure virtual environment is activated

2. **"Permission denied" for Messages Database**:
   - Grant Full Disk Access (see setup instructions above)
   - Or use the file upload alternative

3. **Spotify Authorization Fails**:
   - Check your `.env` file has correct credentials
   - Ensure redirect URI in Spotify app matches: `http://127.0.0.1:8888/callback`
   - ⚠️ **Important**: Use `127.0.0.1`, not `localhost` (Spotify requirement)

4. **"Address already in use" Error**:
   - Kill existing process: `pkill -f uvicorn`
   - Or use a different port: `--port 8889`

5. **Frontend/Backend Connection Issues**:
   - The app serves both frontend and backend from port 8888
   - Check that `website/config.js` has: `const BASE_URL = "http://127.0.0.1:8888";`

## Security Notes

- Your `.env` file contains sensitive credentials - never commit it to version control
- The Messages database contains personal data - handle with care
- All processing happens locally on your machine

## Caching

This project uses an SQLite database to cache metadata for Spotify URLs, stored in the user's home directory at `~/.spotify_cache/spotify_cache.db`. This ensures efficient reuse of metadata and reduces API calls.

To initialize the cache, simply run the script. The cache directory will be created automatically if it doesn't exist.

The cache file is not included in this repository to ensure user privacy and prevent unnecessary commits.

## Documentation

- **[QUICK_START.md](./QUICK_START.md)** - Get started in 5 minutes
- **[TESTING_LOCAL_APP.md](./TESTING_LOCAL_APP.md)** - Testing guide
- **[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)** - Architecture and technical details
- **[docs/](./docs/)** - Additional guides and documentation

## For Developers

> **For Developers**: 
> - See [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) for architecture, database schema, and technical details
> - See [docs/](./docs/) for additional guides and analysis documents

## Useful Resources

- typedstream library to parse Apple-formatted binary https://github.com/dgelessus/python-typedstream
- Other projects that parse iMessage data
    - https://github.com/yortos/imessage-analysis/blob/master/notebooks/imessages-analysis.ipynb
    - https://github.com/caleb531/imessage-conversation-analyzer/tree/167fb9c9a9082df453857f640d60904b30690443
    - BAIB project: https://github.com/arjunpat/treehacks24/blob/eb97a81c97b577e37a85d5dbdfdb2464c9fd7bfa/README.md
- List of music-related APIs: https://musicmachinery.com/music-apis/
