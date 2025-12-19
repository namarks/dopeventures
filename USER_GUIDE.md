# Dopetracks User Guide

Complete guide for end users - from download to creating your first playlist.

## Table of Contents

1. [What is Dopetracks?](#what-is-dopetracks)
2. [System Requirements](#system-requirements)
3. [Download & Setup](#download--setup)
4. [First-Time Configuration](#first-time-configuration)
5. [Using the App](#using-the-app)
6. [Troubleshooting](#troubleshooting)
7. [Security & Privacy](#security--privacy)

---

## What is Dopetracks?

Dopetracks is an app that creates Spotify playlists from songs your friends have shared in iMessage chats.

**Example**: If you have a group chat where people share Spotify songs, Dopetracks can automatically create a playlist with all those songs!

---

## System Requirements

- **macOS** (required - app needs access to Messages database)
- **Spotify Premium account** (required for playlist creation)
- **Internet connection** (for setup and Spotify API)

---

## Download & Setup

### Packaged macOS App (Recommended - Coming Soon!)

1. Download `Dopetracks.dmg` from [GitHub Releases](https://github.com/namarks/dopeventures/releases/latest)
2. Open the DMG file
3. Drag `Dopetracks.app` to your Applications folder
4. Double-click to launch - setup wizard will guide you!

**Note:** If no releases are available yet, developers can use the command-line setup (see [QUICK_START.md](./QUICK_START.md)).

### Get Spotify Credentials (2 minutes)

> **Note:** If using the packaged app, the setup wizard will guide you through this step automatically.

You need to create a free Spotify Developer App:

1. Go to: **https://developer.spotify.com/dashboard**
2. Sign in with your Spotify account
3. Click **"Create App"**
4. Fill in:
   - **App Name**: "Dopetracks" (or any name)
   - **App Description**: "Personal playlist creator"
   - **Redirect URI**: `http://127.0.0.1:8888/callback` ⚠️ **Important**: Use `127.0.0.1`, not `localhost`
   - Check "I understand and agree to the Spotify Developer Terms of Service"
5. Click **"Save"**
6. Copy your **Client ID** and **Client Secret** (you'll need these next)


---

## First-Time Configuration

When you first launch the packaged app, a setup wizard will guide you through:

1. **Spotify Credentials** - Enter your Client ID and Secret
2. **macOS Permissions** - Grant Full Disk Access if needed

### Grant macOS Permissions

To access your Messages database:

1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Full Disk Access** from the left sidebar
3. Click the lock icon 🔒 and enter your password
4. Click the **"+"** button
5. Add **Terminal** (or **Python** if you have it)
6. Make sure the checkbox is checked

> **Alternative**: If you don't want to grant Full Disk Access, you can manually copy your Messages database and upload it through the web interface.

---

## Using the App

### Step 1: Launch

1. **Double-click** `Dopetracks.app` in your Applications folder
2. Your browser will open automatically to **http://127.0.0.1:8888**
3. If it doesn't open automatically, navigate to that URL manually

### Step 2: Authorize Spotify (One-Time)

1. Click **"Connect to Spotify"** button
2. You'll be redirected to Spotify to authorize the app
3. Click **"Agree"** to grant permissions
4. You'll be redirected back to the app

### Step 3: Search for Chats

1. Use the search box to find chats by:
   - Chat name
   - Participant name
   - Phone number or email
2. Select the chats you want to include by checking the boxes

### Step 4: Create Your Playlist

1. **Choose date range**: Select start and end dates for messages to include
2. **Enter playlist name**: Give your playlist a name
3. **Click "Create Playlist"**: Watch the progress as tracks are added!
4. **Open on Spotify**: Click the link to view your new playlist

---

## Troubleshooting


### "Server won't start"

- Port 8888 might be in use by another app
- Close other apps using that port
- Or manually kill: `pkill -f uvicorn`
- Or restart your computer

### "Permission denied" for Messages Database

- Grant Full Disk Access (see First-Time Configuration section)
- Or use the file upload alternative:
  1. Copy your Messages database: `cp ~/Library/Messages/chat.db ./my_messages.db`
  2. Use the file upload feature in the web interface

### "Spotify authorization fails"

- Check your `.env` file has correct credentials
- Ensure redirect URI in Spotify app matches exactly: `http://127.0.0.1:8888/callback`
- ⚠️ **Important**: Use `127.0.0.1`, not `localhost` (Spotify requirement)
- Make sure you saved the `.env` file after editing


### Browser doesn't open automatically

- Manually open: **http://127.0.0.1:8888**
- Check the launcher log for errors
- Make sure the server started successfully

---

## Security & Privacy

### Is It Safe?

- ✅ **All data stays on your computer** - Nothing is uploaded to external servers
- ✅ **Open source** - You can see all the code on GitHub
- ✅ **No tracking** - The app doesn't collect any analytics or user data
- ✅ **Local only** - Runs entirely on your Mac

### What Gets Stored?

- **Spotify tokens**: Stored locally in `~/.dopetracks/local.db` (encrypted)
- **Configuration**: Your `.env` file contains Spotify credentials (keep it private!)
- **Cache**: Spotify metadata cache at `~/.spotify_cache/spotify_cache.db`

### Best Practices

- **Never commit `.env` file** - It contains sensitive credentials
- **Keep your Messages database private** - It contains personal conversations
- **Use strong passwords** - If you set up user accounts (future feature)

---

## Next Steps

After you've created your first playlist:

- Try creating playlists from different date ranges
- Experiment with combining multiple chats
- Check out the track details to see who shared what

## Need More Help?

- See **[QUICK_START.md](./QUICK_START.md)** for quick reference
- See **[README.md](./README.md)** for overview and links
- See **[docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)** for detailed troubleshooting
- Open an issue on [GitHub](https://github.com/namarks/dopeventures) if you encounter problems

---

## Summary

**To use Dopetracks:**
1. Download `Dopetracks.dmg` from [GitHub Releases](https://github.com/namarks/dopeventures/releases/latest)
2. Install the app to Applications
3. Launch and follow the setup wizard
4. Create playlists!

**That's it!** No coding required, no complex setup - just download, install, and use.

