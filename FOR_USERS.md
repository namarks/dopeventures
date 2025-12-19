# Dopetracks - User Guide

## What is This?

Dopetracks is an app that creates Spotify playlists from songs your friends have shared in iMessage chats. 

**Example**: If you have a group chat where people share Spotify songs, Dopetracks can automatically create a playlist with all those songs!

## How Do I Get It?

### Download Method (Easiest)

1. **Go to GitHub**: https://github.com/namarks/dopeventures
2. **Click "Code"** (green button, top right)
3. **Click "Download ZIP"**
4. **Extract** the ZIP file (double-click it)
5. **Move** the `dopeventures` folder to your Desktop or Applications folder

That's it! You now have the app.

## How Do I Use It?

### First Time Setup (5 minutes)

1. **Double-click** `Launch Dopetracks.command` in the `dopeventures` folder
   - macOS might ask if you want to open it - click "Open"

2. **Get Spotify Credentials** (2 minutes):
   - Go to https://developer.spotify.com/dashboard
   - Sign in with your Spotify account
   - Click "Create App"
   - Fill in:
     - Name: "Dopetracks"
     - Redirect URI: `http://127.0.0.1:8888/callback`
   - Click "Save"
   - Copy your **Client ID** and **Client Secret**

3. **Add Credentials to App**:
   - The launcher will create a `.env` file
   - Open it in a text editor (TextEdit works)
   - Replace `your_client_id_here` with your Client ID
   - Replace `your_client_secret_here` with your Client Secret
   - Save the file

4. **Launch**:
   - Click "Launch App" (or press Enter)
   - Browser opens automatically
   - Click "Connect to Spotify" and authorize

### Using the App

1. **Authorize Spotify** (one-time, if not done)
2. **Search for Chats**: Type a chat name or person's name
3. **Select Chats**: Check the boxes for chats you want
4. **Choose Dates**: Pick start and end date
5. **Create Playlist**: Click "Create Playlist" and watch it build!

## What Do I Need?

- **macOS** (the app needs access to your Messages database)
- **Python 3.11+** (usually already installed on macOS)
- **Spotify Premium** (required to create playlists)
- **Internet connection** (for setup and Spotify)

## What Gets Installed?

When you first run the app:
- Creates a virtual environment (isolated Python environment)
- Installs required packages (FastAPI, pandas, etc.)
- Creates a local database (`~/.dopetracks/local.db`)
- Stores your Spotify tokens securely

**Nothing is installed system-wide** - everything stays in the `dopeventures` folder.

## Troubleshooting

### "Can't open .command file"
- Right-click the file → Open With → Terminal
- Or: System Preferences → Security → Allow apps from anywhere

### "Python not found"
- Install Python from python.org
- Or use Homebrew: `brew install python3`

### "Setup fails"
- Check your internet connection
- Make sure Python 3.11+ is installed
- Check the launcher window for error messages

### "Server won't start"
- Another app might be using port 8888
- Close other apps or restart your computer

## Is It Safe?

- ✅ **All data stays on your computer** - nothing is uploaded
- ✅ **Open source** - you can see all the code
- ✅ **No tracking** - the app doesn't collect any data
- ✅ **Local only** - runs entirely on your Mac

## Next Steps

After downloading:
1. See [DOWNLOAD_INSTRUCTIONS.md](./DOWNLOAD_INSTRUCTIONS.md) for detailed setup
2. See [QUICK_START.md](./QUICK_START.md) for quick reference
3. See [README.md](./README.md) for full documentation

## Summary

**To use Dopetracks:**
1. Download ZIP from GitHub
2. Extract and double-click `Launch Dopetracks.command`
3. Get Spotify credentials (free, 2 minutes)
4. Add credentials to `.env` file
5. Launch and use!

**That's it!** No coding required, no complex setup - just download, configure Spotify, and use.

