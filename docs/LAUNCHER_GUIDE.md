# Launcher Guide

Guide for using the Dopetracks launcher applications.

## Available Launchers

### CLI Launcher (`launch.py`)

Simple command-line launcher that checks setup and launches the app.

**Usage:**
```bash
python3 scripts/launch/launch.py          # Check setup and launch
python3 scripts/launch/launch.py --setup  # Run setup only
```

**Features:**
- Checks setup status
- Runs setup if needed
- Launches the app
- Automatic browser opening

---

## First Time Setup

### Using the Launcher

1. **Run the launcher**:
   ```bash
   python3 scripts/launch/launch.py
   ```

2. **Setup**:
   - Launcher will automatically detect if setup is needed
   - Creates virtual environment
   - Installs dependencies
   - Creates `.env` file template
   - Creates `config.js`

3. **Add Spotify Credentials**:
   - Edit the `.env` file
   - Add your Spotify Client ID and Secret
   - See setup instructions in the launcher output

4. **Launch**:
   - Press Enter when prompted
   - Server starts automatically
   - Browser opens to http://127.0.0.1:8888

### Alternative: Manual Setup

```bash
./setup.sh
# Edit .env file with Spotify credentials
python3 start.py
```

---

## Subsequent Launches

### Using the Launcher

Run:
```bash
python3 scripts/launch/launch.py
```

Press Enter when prompted - no setup needed if already configured!

### Direct Launch (Advanced)

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

- **Start Server**: Press Enter in launcher
- **Stop Server**: Press Ctrl+C in the terminal

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
- Kill existing server: `pkill -f uvicorn`
- Try launching again


### Browser doesn't open

- Manually open: http://127.0.0.1:8888
- Check the launcher log for errors

### Launcher issues

The launcher is CLI-only. If you encounter issues:

```bash
# Check Python version
python3 --version  # Should be 3.11+

# Run setup manually
./setup.sh

# Or launch directly
source venv/bin/activate
python3 start.py
```

---

## Testing the Launcher

For detailed testing instructions, see the testing section in **[DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)**.

---

## Creating a macOS App Bundle

Dopetracks can be packaged as a standalone macOS app using PyInstaller. See **[PACKAGING.md](./PACKAGING.md)** for complete instructions.

**Quick build:**
```bash
./build/build_mac_app.sh
```

This creates `dist/Dopetracks.app` - a self-contained app bundle that doesn't require Python installation.

---

## Advanced Usage

### Custom Port

Edit `start.py` or `scripts/launch/launch.py` to change the port:
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
1. Run `python3 scripts/launch/launch.py`
2. Press Enter when prompted
3. Use the app!

**That's it!** The launcher handles everything else automatically.

