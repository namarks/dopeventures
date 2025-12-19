# How to Use Dopetracks

## For End Users (Non-Developers)

### Option 1: Download from GitHub (Current Method)

1. **Download the App**:
   - Go to: https://github.com/namarks/dopeventures
   - Click the green **"Code"** button
   - Select **"Download ZIP"**
   - Extract the ZIP file to your desired location (e.g., Desktop, Applications folder)

2. **Get Spotify Credentials** (One-time setup, 2 minutes):
   - Go to https://developer.spotify.com/dashboard
   - Click **"Create App"**
   - Fill in:
     - App Name: "Dopetracks" (or any name)
     - Redirect URI: `http://127.0.0.1:8888/callback`
   - Click **"Save"**
   - Copy your **Client ID** and **Client Secret**

3. **Launch the App**:
   - **Double-click** `Launch Dopetracks.command` in the extracted folder
   - If prompted, click "Open" (macOS may warn about opening downloaded files)
   - The launcher will:
     - Set up everything automatically (first time only)
     - Ask you to add Spotify credentials to `.env` file
     - Launch the app and open your browser

4. **Use the App**:
   - Authorize Spotify (one-time)
   - Search for chats
   - Create playlists!

### Option 2: Clone with Git (For Developers)

```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures
./setup.sh
# Edit .env file with Spotify credentials
python3 start.py
```

## What They Need

### Prerequisites:
- **macOS** (required - app needs access to Messages database)
- **Python 3.11+** (usually pre-installed on macOS)
- **Spotify Premium account**
- **Internet connection** (for setup and Spotify API)

### What Gets Downloaded:
- All source code
- Setup scripts
- Launcher scripts
- Documentation

### What Gets Created (After Setup):
- Virtual environment (`venv/` folder)
- Configuration file (`.env`)
- Local database (`~/.dopetracks/local.db`)

## Step-by-Step for New Users

### First Time Setup:

1. **Download**:
   ```
   GitHub → Code → Download ZIP
   Extract to Desktop or Applications
   ```

2. **Open the Folder**:
   - Find `dopeventures` folder
   - Double-click `Launch Dopetracks.command`

3. **Follow the Prompts**:
   - Launcher checks setup
   - If setup needed, it runs automatically
   - You'll be prompted to add Spotify credentials

4. **Add Spotify Credentials**:
   - Launcher opens `.env` file (or you can find it in the folder)
   - Replace `your_client_id_here` with your actual Client ID
   - Replace `your_client_secret_here` with your actual Client Secret
   - Save the file

5. **Launch**:
   - Click "Launch App" (or press Enter in simple launcher)
   - Browser opens automatically
   - You're ready to use Dopetracks!

### Subsequent Uses:

Just double-click `Launch Dopetracks.command` - that's it!

## Making It Even Easier (Future Improvements)

### Option A: Create a DMG Installer
- Package everything in a `.dmg` file
- Users double-click to "install" (just copy to Applications)
- Includes instructions in the DMG

### Option B: Create a Standalone App Bundle
- Use PyInstaller to create a single `.app` file
- Users just double-click the app
- Everything bundled inside

### Option C: Create an Installer Script
- Simple installer that:
  - Downloads/clones the repo
  - Runs setup
  - Creates shortcuts
  - Guides through Spotify setup

## Current Limitations

- Users need to:
  - Have Python installed (usually pre-installed on macOS)
  - Get Spotify developer credentials (free, but requires signup)
  - Grant Full Disk Access (for Messages database)

## What Happens Behind the Scenes

When a user launches the app:

1. **Setup Phase** (first time only):
   - Creates Python virtual environment
   - Installs dependencies (FastAPI, pandas, spotipy, etc.)
   - Creates configuration files

2. **Launch Phase**:
   - Starts FastAPI server on port 8888
   - Serves web interface
   - Opens browser automatically

3. **Usage**:
   - All interaction through web browser
   - No command line needed
   - Server runs until user closes it

## Troubleshooting for Users

### "Can't open .command file"
- Right-click → Open With → Terminal
- Or: System Preferences → Security → Allow

### "Python not found"
- Install Python from python.org
- Or use Homebrew: `brew install python3`

### "Setup fails"
- Check internet connection
- Make sure Python 3.11+ is installed
- Check the launcher log for specific errors

### "Server won't start"
- Port 8888 might be in use
- Close other apps using that port
- Or manually kill: `pkill -f uvicorn`

