# Quick Start Guide

Get Dopetracks running in 5 minutes!

> **For end users**: Use the packaged macOS app (see [USER_GUIDE.md](./USER_GUIDE.md))  
> **For developers**: Follow this guide to set up from source code

## Prerequisites

- **macOS** (required for Messages database access)
- **Python 3.11+**
- **Spotify Premium account**
- **Spotify Developer App** (free, takes 2 minutes to create)

## Step 1: Clone and Setup (2 minutes)

```bash
# Clone the repository
git clone https://github.com/namarks/dopeventures.git
cd dopeventures

# Run the setup script
./setup.sh
```

The setup script will:
- ✅ Create a virtual environment
- ✅ Install all dependencies
- ✅ Create a `.env` file template
- ✅ Configure Spotify credentials in `.env`

## Step 2: Get Spotify Credentials (2 minutes)

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **"Create App"**
3. Fill in:
   - **App Name**: "Dopetracks" (or any name)
   - **App Description**: "Personal playlist creator"
   - **Redirect URI**: `http://127.0.0.1:8888/callback`
   - Check the Terms of Service box
4. Click **"Save"**
5. Copy your **Client ID** and **Client Secret**

## Step 3: Configure (1 minute)

Edit the `.env` file and add your credentials:

```bash
# Open .env in your editor
nano .env  # or use your preferred editor
```

Replace the placeholder values:
```
SPOTIFY_CLIENT_ID=your_actual_client_id_here
SPOTIFY_CLIENT_SECRET=your_actual_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

## Step 4: Grant macOS Permissions (1 minute)

To access your Messages database:

1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Full Disk Access** from the left sidebar
3. Click the lock icon 🔒 and enter your password
4. Click the **"+"** button
5. Add **Terminal** (or **Python** if you have it)
6. Make sure the checkbox is checked

> **Alternative**: If you don't want to grant Full Disk Access, you can manually copy your Messages database and upload it through the web interface.

## Step 5: Run the App

```bash
# Activate virtual environment
source venv/bin/activate

# Start the app
python3 dev_server.py
```

You should see:
```
🚀 Starting Dopetracks Application...
📍 Health check: http://127.0.0.1:8888/health
🌐 Application: http://127.0.0.1:8888
```

## Step 6: Use the App

1. **Open the Swift app**: Open `DopetracksApp/DopetracksApp.xcodeproj` in Xcode and run
2. **Authorize Spotify**: Click "Connect to Spotify" and complete OAuth
3. **Verify System Access**: The app will auto-detect your Messages database
4. **Search Chats**: Search for chat names or participant names
5. **Create Playlist**: Select chats, choose dates, and create your playlist!

## Troubleshooting

### "No module named 'packages'"
- Make sure you're in the project root directory
- Activate the virtual environment: `source venv/bin/activate`

### "Permission denied" for Messages
- Grant Full Disk Access (see Step 4)
- Or upload your database file manually through the web interface

### "Spotify authorization fails"
- Check your `.env` file has correct credentials
- Make sure redirect URI is exactly: `http://127.0.0.1:8888/callback`
- Don't use `localhost` - use `127.0.0.1`

### Port already in use
```bash
# Kill the process using port 8888
lsof -ti:8888 | xargs kill -9
```

## What's Next?

- See [README.md](./README.md) for detailed documentation
- See [docs/TESTING_LOCAL_APP.md](./docs/TESTING_LOCAL_APP.md) for testing guide
- Check the `/health` endpoint to verify everything is working

## Need Help?

- Check the [README.md](./README.md) for detailed instructions
- Review [docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md) for common issues
- Open an issue on GitHub if you encounter problems

