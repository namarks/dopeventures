# Launcher Guide

Guide for using the Dopetracks launcher applications.

## Available Launchers

### 1. GUI Launcher (`launch.py`)

The easiest way to launch Dopetracks with a graphical interface.

**Usage:**
```bash
python3 launch.py
```

Or double-click `Launch Dopetracks.command` which automatically runs the GUI launcher.

**Features:**
- Visual status indicators
- One-click setup
- One-click launch
- Server management (start/stop)
- Automatic browser opening

### 2. Simple Launcher (`launch_simple.py`)

A minimal command-line launcher for quick access.

**Usage:**
```bash
python3 launch_simple.py
```

**Features:**
- Checks setup status
- Prompts for launch
- Minimal output

### 3. Command File (`Launch Dopetracks.command`)

A macOS command file that opens the GUI launcher.

**Usage:**
Double-click in Finder, or:
```bash
./Launch\ Dopetracks.command
```

---

## First Time Setup

### Using GUI Launcher

1. **Run the launcher**:
   ```bash
   python3 launch.py
   ```

2. **Click "Setup (First Time)"**:
   - Creates virtual environment
   - Installs dependencies
   - Creates `.env` file template
   - Creates `config.js`

3. **Add Spotify Credentials**:
   - Launcher will prompt you
   - Edit the `.env` file
   - Add your Spotify Client ID and Secret

4. **Click "Launch App"**:
   - Server starts automatically
   - Browser opens to http://127.0.0.1:8888

### Using Command Line

```bash
./setup.sh
# Edit .env file with Spotify credentials
python3 start.py
```

---

## Subsequent Launches

### GUI Launcher

Just double-click `Launch Dopetracks.command` or run:
```bash
python3 launch.py
```

Then click "Launch App" - no setup needed!

### Command Line

```bash
source venv/bin/activate
python3 start.py
```

---

## Launcher Features

### Setup Detection

The launcher automatically checks:
- ✅ Virtual environment exists
- ✅ Dependencies installed
- ✅ `.env` file configured
- ✅ `config.js` exists

### Server Management

- **Start Server**: Click "Launch App" button
- **Stop Server**: Click "Stop Server" button
- **Status**: Shows server status in log area

### Automatic Browser Opening

The launcher automatically opens your browser to:
- http://127.0.0.1:8888

---

## Troubleshooting

### "Python not found"

- Make sure Python 3.11+ is installed
- On macOS, you may need to install from python.org
- Check: `python3 --version`

### "Virtual environment not found"

- Click "Setup (First Time)" in the launcher
- Or run `./setup.sh` manually

### "Server won't start"

- Check if port 8888 is already in use
- Click "Stop Server" and try again
- Or manually kill: `pkill -f uvicorn`

### "Can't open .command file"

- Right-click → Open With → Terminal
- Or run: `chmod +x "Launch Dopetracks.command"`
- Or run directly: `python3 launch.py`

### Browser doesn't open

- Manually open: http://127.0.0.1:8888
- Check the launcher log for errors

### GUI doesn't open

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Check tkinter
python3 -c "import tkinter; print('OK')"

# Try running directly
python3 launch.py
```

---

## Testing the Launcher

For detailed testing instructions, see the testing section in **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)**.

---

## Creating a macOS App Bundle

Dopetracks can be packaged as a standalone macOS app using PyInstaller. See **[PACKAGING.md](../PACKAGING.md)** for complete instructions.

**Quick build:**
```bash
./build_mac_app.sh
```

This creates `dist/Dopetracks.app` - a self-contained app bundle that doesn't require Python installation.

---

## Advanced Usage

### Custom Port

Edit `start.py` or `launch.py` to change the port:
```python
uvicorn.run(app, host="0.0.0.0", port=8889)
```

### Custom Environment

Set environment variables before launching:
```bash
export DATABASE_URL="sqlite:///./custom.db"
python3 start.py
```

---

## Summary

**Easiest Method:**
1. Double-click `Launch Dopetracks.command`
2. Click "Launch App"
3. Use the app!

**That's it!** The launcher handles everything else automatically.

