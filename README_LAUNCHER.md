# No-Code Setup: Using the Launcher

Dopetracks can be launched without using the command line! Use the GUI launcher instead.

## Option 1: Double-Click Launcher (Easiest!)

**On macOS, just double-click:**
- **`Launch Dopetracks.command`** - Opens the GUI launcher automatically

That's it! The GUI will guide you through setup and launching.

## Option 2: GUI Launcher

### First Time Setup:

1. **Double-click `launch.py`** (or run `python3 launch.py`)

2. **Click "Setup (First Time)"** button
   - This will automatically:
     - Create virtual environment
     - Install dependencies
     - Create .env file
     - Create config.js

3. **Add Spotify Credentials**:
   - The launcher will prompt you
   - Edit the `.env` file (it will open automatically or you can find it in the project folder)
   - Add your Spotify Client ID and Secret from https://developer.spotify.com/dashboard

4. **Click "Launch App"** button
   - Server starts automatically
   - Browser opens to http://127.0.0.1:8888
   - You're ready to use Dopetracks!

### Subsequent Launches:

Just double-click `Launch Dopetracks.command` or `launch.py` and click "Launch App" - that's it!

## Option 3: Create a macOS App Bundle

You can create a double-clickable macOS app:

1. **Open Automator** (Applications → Automator)

2. **Create New Application**

3. **Add "Run Shell Script" action**:
   ```bash
   cd /path/to/dopeventures
   source venv/bin/activate
   python3 start.py &
   sleep 5
   open http://127.0.0.1:8888
   ```

4. **Save as "Dopetracks.app"**

5. **Double-click to launch!**

## Troubleshooting

### "Python not found"
- Make sure Python 3.11+ is installed
- On macOS, you may need to install from python.org

### "Virtual environment not found"
- Click "Setup (First Time)" in the launcher
- Or run `./setup.sh` manually

### "Server won't start"
- Check if port 8888 is already in use
- Click "Stop Server" and try again
- Or manually kill: `pkill -f uvicorn`

### Browser doesn't open
- Manually open: http://127.0.0.1:8888
- Check the launcher log for errors

### "Can't open .command file"
- Right-click the file → Open With → Terminal
- Or run: `chmod +x "Launch Dopetracks.command"`
