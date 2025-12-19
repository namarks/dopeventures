# Download and Use Dopetracks

## Quick Download Guide

### Step 1: Download

1. Go to: **https://github.com/namarks/dopeventures**
2. Click the green **"Code"** button (top right)
3. Click **"Download ZIP"**
4. Extract the ZIP file to your Desktop or Applications folder

### Step 2: Get Spotify Credentials (2 minutes)

1. Go to: **https://developer.spotify.com/dashboard**
2. Sign in with your Spotify account
3. Click **"Create App"**
4. Fill in:
   - **App Name**: "Dopetracks" (or any name)
   - **App Description**: "Personal playlist creator"
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
   - Check "I understand and agree..."
5. Click **"Save"**
6. Copy your **Client ID** and **Client Secret** (you'll need these in Step 4)

### Step 3: Launch

1. Open the `dopeventures` folder you extracted
2. **Double-click** `Launch Dopetracks.command`
3. If macOS asks, click **"Open"** (it's safe - it's just a launcher script)

### Step 4: First-Time Setup

The launcher will:
1. Check if setup is needed
2. If needed, click **"Setup (First Time)"** or run setup automatically
3. Wait for setup to complete (installs dependencies - takes 1-2 minutes)

### Step 5: Add Spotify Credentials

1. The launcher will prompt you to edit the `.env` file
2. Open the `.env` file in the `dopeventures` folder (use TextEdit or any text editor)
3. Find these lines:
   ```
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   ```
4. Replace `your_client_id_here` with your actual Client ID from Step 2
5. Replace `your_client_secret_here` with your actual Client Secret from Step 2
6. Save the file

### Step 6: Launch and Use!

1. Click **"Launch App"** (or press Enter)
2. Your browser will open automatically to http://127.0.0.1:8888
3. Click **"Connect to Spotify"** and authorize
4. Start creating playlists!

## What You're Downloading

- **Source code** - The app itself
- **Setup scripts** - Automatically configure everything
- **Launcher** - Easy way to start the app
- **Documentation** - Help files and guides

## System Requirements

- **macOS** (required - app needs Messages database)
- **Python 3.11+** (usually pre-installed)
- **Spotify Premium** (required for playlist creation)
- **Internet connection** (for setup)

## File Structure

After downloading and extracting:

```
dopeventures/
├── Launch Dopetracks.command  ← Double-click this!
├── launch_simple.py           ← Alternative launcher
├── setup.sh                   ← Setup script (runs automatically)
├── start.py                   ← Main app (launcher runs this)
├── .env                       ← Your Spotify credentials (you edit this)
└── ... (other files)
```

## Next Time You Use It

Just double-click `Launch Dopetracks.command` - no setup needed!

## Need Help?

- See [QUICK_START.md](./QUICK_START.md) for detailed setup
- See [README.md](./README.md) for full documentation
- See [HOW_TO_USE.md](./HOW_TO_USE.md) for usage guide

