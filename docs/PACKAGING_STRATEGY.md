# Packaging Strategy: Native macOS App Distribution

## Executive Summary

Transform Dopetracks from a GitHub-based Python application into a downloadable `.dmg` file that users can install like any macOS app. The app will include:
- Embedded Python runtime (no user Python installation needed)
- Built-in setup wizard for Spotify OAuth configuration
- Automatic Messages database detection
- Native macOS app bundle with proper permissions handling
- Self-contained web server (no external dependencies)

## Recommended Approach: PyInstaller + Native GUI Launcher

### Why PyInstaller?
- ✅ Bundles Python interpreter and all dependencies
- ✅ Creates single executable or app bundle
- ✅ Works well with FastAPI/uvicorn
- ✅ Can include data files (frontend, config templates)
- ✅ Cross-platform (though we only need macOS)
- ✅ Active maintenance and good documentation

### Alternative: Py2App (macOS-specific)
- ✅ More macOS-native (proper .app bundle structure)
- ✅ Better integration with macOS permissions
- ✅ Can request Full Disk Access automatically
- ❌ macOS-only (not a problem for this app)
- ❌ Less active development

**Recommendation: Start with PyInstaller, consider Py2App if macOS-specific features are needed.**

## Architecture

### App Structure
```
Dopetracks.app/
├── Contents/
│   ├── MacOS/
│   │   └── dopetracks          # Main executable (bundled Python + app)
│   ├── Resources/
│   │   ├── website/            # Frontend files
│   │   ├── config_template.env  # Template for .env
│   │   └── icon.icns           # App icon
│   └── Info.plist             # macOS app metadata
└── Frameworks/                # Python runtime and dependencies
```

### User Data Location
- Config: `~/Library/Application Support/Dopetracks/.env`
- Database: `~/Library/Application Support/Dopetracks/local.db`
- Logs: `~/Library/Logs/Dopetracks/backend.log`

## Implementation Plan

### Phase 1: Setup Wizard GUI
**Goal**: Replace manual `.env` editing with guided setup

**Components**:
1. **First Launch Detection**
   - Check if config exists in `~/Library/Application Support/Dopetracks/`
   - If not, launch setup wizard

2. **Setup Wizard Flow**:
   ```
   Step 1: Welcome Screen
   - Explain what Dopetracks does
   - Explain Spotify OAuth requirement
   
   Step 2: Spotify Developer Setup
   - Instructions to create Spotify app
   - Link to https://developer.spotify.com/dashboard
   - "I've created my app" button
   
   Step 3: Enter Credentials
   - Client ID input field
   - Client Secret input field (masked)
   - Validate format (Client ID: 32 chars, Secret: 32 chars)
   - Test connection button
   
   Step 4: Permissions Check
   - Check Full Disk Access permission
   - Instructions if not granted
   - "Open System Preferences" button
   
   Step 5: Messages Database Detection
   - Auto-detect: ~/Library/Messages/chat.db
   - Or allow manual path selection
   - Validate database accessibility
   
   Step 6: Complete
   - Save config to ~/Library/Application Support/Dopetracks/.env
   - Launch app button
   ```

3. **GUI Framework Options**:
   - **Option A: Tkinter** (built-in, simple)
     - ✅ No extra dependencies
     - ✅ Already used in launch.py
     - ❌ Not native-looking
   
   - **Option B: PyQt/PySide** (native-looking)
     - ✅ Better UX, native macOS appearance
     - ❌ Larger bundle size
     - ❌ License considerations (PySide is LGPL)
   
   - **Option C: Web-based wizard** (FastAPI + embedded browser)
     - ✅ Reuse existing frontend skills
     - ✅ Consistent with app architecture
     - ✅ Can be accessed later for reconfiguration
     - ✅ Best option for maintainability

**Recommendation: Option C (Web-based wizard)** - Serve setup wizard on port 8889, launch in system browser, then redirect to main app on 8888 after setup.

### Phase 2: PyInstaller Configuration

**File: `build/build_app.spec`**
```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['scripts/launch/launch_bundled.py'],  # Entry point
    pathex=[],
    binaries=[],
    datas=[
        ('website', 'website'),  # Include frontend
        ('packages', 'packages'),  # Include Python package
        ('config_template.env', '.'),  # Config template
    ],
    hiddenimports=[
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.http.httptools_impl',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.logging',
        'fastapi',
        'sqlalchemy',
        'spotipy',
        'pandas',
        'numpy',
        'pytypedstream',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Dopetracks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='Dopetracks.app',
    icon='resources/icon.icns',  # App icon
    bundle_identifier='com.dopetracks.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': False,
        'LSMinimumSystemVersion': '10.15',  # macOS Catalina+
        'NSFullDiskAccessUsageDescription': 'Dopetracks needs Full Disk Access to read your Messages database and create Spotify playlists from shared songs.',
    },
)
```

### Phase 3: Bundled Launcher Script

**File: `scripts/launch/launch_bundled.py`** (replaces start.py for bundled app)
```python
#!/usr/bin/env python3
"""
Bundled app launcher - handles setup wizard and app startup.
"""
import sys
import os
from pathlib import Path
import webbrowser
import threading
import time
import uvicorn

# Determine if running as bundled app
if getattr(sys, 'frozen', False):
    # Running as bundled executable
    APP_DIR = Path(sys._MEIPASS)  # PyInstaller temp directory
    BASE_DIR = Path(os.path.expanduser('~'))
else:
    # Running as script
    APP_DIR = Path(__file__).parent
    BASE_DIR = APP_DIR

# User data directory (persistent across app updates)
USER_DATA_DIR = BASE_DIR / 'Library' / 'Application Support' / 'Dopetracks'
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = USER_DATA_DIR / '.env'
DATABASE_DIR = USER_DATA_DIR
LOG_DIR = BASE_DIR / 'Library' / 'Logs' / 'Dopetracks'
LOG_DIR.mkdir(parents=True, exist_ok=True)

def check_setup_complete():
    """Check if app is fully configured."""
    if not CONFIG_FILE.exists():
        return False
    
    # Check if config has real credentials
    with open(CONFIG_FILE) as f:
        content = f.read()
        if 'your_client_id_here' in content or not content.strip():
            return False
    
    # Validate Spotify credentials are present
    env_vars = {}
    for line in content.split('\n'):
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            env_vars[key.strip()] = value.strip()
    
    return bool(env_vars.get('SPOTIFY_CLIENT_ID') and env_vars.get('SPOTIFY_CLIENT_SECRET'))

def launch_setup_wizard():
    """Launch setup wizard web interface."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    
    setup_app = FastAPI()
    
    @setup_app.get("/", response_class=HTMLResponse)
    async def setup_wizard():
        # Serve setup wizard HTML
        # (Implementation details in next section)
        pass
    
    # Run setup wizard on port 8889
    def run_setup():
        uvicorn.run(setup_app, host="127.0.0.1", port=8889, log_level="error")
    
    threading.Thread(target=run_setup, daemon=True).start()
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8889")
    
    # Wait for setup to complete
    print("Setup wizard opened. Complete the setup, then press Enter...")
    input()

def launch_main_app():
    """Launch the main Dopetracks application."""
    # Set environment variables from config
    if CONFIG_FILE.exists():
        from dotenv import load_dotenv
        load_dotenv(CONFIG_FILE, override=True)
    
    # Set database path
    os.environ['DATABASE_URL'] = f"sqlite:///{DATABASE_DIR / 'local.db'}"
    
    # Add packages to path
    packages_dir = APP_DIR / 'packages'
    if packages_dir.exists():
        sys.path.insert(0, str(packages_dir))
    
    # Import and run app
    from dopetracks.app import app
    
    print("🚀 Starting Dopetracks...")
    print("🌐 Opening http://127.0.0.1:8888")
    
    # Open browser after short delay
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8888")
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run app
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8888,
        log_level="info",
        access_log=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "file": {
                    "class": "logging.FileHandler",
                    "filename": str(LOG_DIR / "backend.log"),
                    "formatter": "default",
                },
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["file", "console"],
            },
        },
    )

def main():
    """Main entry point."""
    if not check_setup_complete():
        print("First-time setup required...")
        launch_setup_wizard()
    
    launch_main_app()

if __name__ == "__main__":
    main()
```

### Phase 4: Setup Wizard Web Interface

**New endpoint in app.py or separate setup_app.py**:
```python
# Setup wizard endpoints
@app.get("/setup", response_class=HTMLResponse)
async def setup_wizard():
    """Setup wizard HTML page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dopetracks Setup</title>
        <style>
            /* Modern, native-looking styles */
        </style>
    </head>
    <body>
        <div class="setup-container">
            <h1>🎵 Welcome to Dopetracks</h1>
            <div id="setup-steps">
                <!-- Multi-step wizard -->
            </div>
        </div>
        <script>
            // Setup wizard logic
            // - Validate Spotify credentials
            // - Test connection
            // - Save config
            // - Check permissions
        </script>
    </body>
    </html>
    """
```

### Phase 5: Build Script

**File: `build/build_mac_app.sh`**
```bash
#!/bin/bash
# Build macOS app bundle

set -e

echo "🔨 Building Dopetracks macOS App..."

# Clean previous builds
rm -rf build/ dist/ Dopetracks.app

# Install PyInstaller if needed
pip install pyinstaller

# Build app
pyinstaller build/build_app.spec

# Create .dmg
echo "📦 Creating DMG..."
hdiutil create -volname "Dopetracks" -srcfolder "dist/Dopetracks.app" -ov -format UDZO "dist/Dopetracks.dmg"

echo "✅ Build complete! DMG: dist/Dopetracks.dmg"
```

## User Experience Flow

### First Launch
1. User downloads `Dopetracks.dmg`
2. User drags `Dopetracks.app` to Applications
3. User double-clicks `Dopetracks.app`
4. **Setup wizard opens automatically** (if not configured)
5. User follows guided setup:
   - Creates Spotify app (with instructions)
   - Enters credentials
   - Grants Full Disk Access (with instructions)
6. App launches, browser opens to `http://127.0.0.1:8888`
7. User can immediately start using the app

### Subsequent Launches
1. User double-clicks `Dopetracks.app`
2. App checks configuration
3. If valid, launches immediately
4. Browser opens to app
5. User uses app

### Reconfiguration
- Settings menu in app → "Reconfigure Spotify" → Opens setup wizard again

## Technical Considerations

### Backend Perspective
- **Error Handling**: Setup wizard must validate Spotify credentials before saving
- **Security**: Store credentials securely (encrypted keychain on macOS)
- **Async Operations**: Setup wizard should test Spotify connection asynchronously
- **Configuration Management**: Use `~/Library/Application Support/` for user data (macOS standard)

### DevOps Perspective
- **Environment Variables**: Load from user data directory, not project directory
- **Logging**: Write to `~/Library/Logs/Dopetracks/` (macOS standard)
- **Database**: Store in user data directory
- **Updates**: Consider auto-update mechanism (Sparkle framework for macOS)
- **Code Signing**: Sign app for distribution (required for Gatekeeper)
- **Notarization**: Notarize with Apple for distribution outside App Store

### Product Perspective
- **Edge Cases**:
  - What if user closes setup wizard mid-setup?
  - What if Spotify credentials are invalid?
  - What if Full Disk Access is denied?
  - What if Messages database doesn't exist?
- **User Intent**:
  - Users want zero configuration
  - Users don't want to edit files
  - Users want clear error messages
  - Users want to know what permissions are needed and why

## Distribution Options

### Option 1: Direct Download (Recommended)
- Host `.dmg` on website/GitHub Releases
- Users download and install
- **Pros**: Full control, no App Store restrictions
- **Cons**: Users must trust download source

### Option 2: Mac App Store
- Submit to Mac App Store
- **Pros**: Trusted source, automatic updates
- **Cons**: Sandbox restrictions (may conflict with Messages DB access), review process, revenue share

### Option 3: Homebrew Cask
- Create Homebrew formula
- Users install via `brew install --cask dopetracks`
- **Pros**: Developer-friendly users, easy updates
- **Cons**: Requires Homebrew, less mainstream

**Recommendation: Start with Option 1 (Direct Download), consider Option 3 for power users.**

## Implementation Checklist

- [ ] Create setup wizard web interface
- [ ] Create bundled launcher script (`scripts/launch/launch_bundled.py`)
- [ ] Create PyInstaller spec file
- [ ] Test PyInstaller build locally
- [ ] Create app icon (`.icns` file)
- [ ] Configure Info.plist with proper permissions
- [ ] Test first-launch flow
- [ ] Test subsequent launches
- [ ] Test reconfiguration flow
- [ ] Create build script
- [ ] Test on clean macOS system (no Python installed)
- [ ] Code sign app bundle
- [ ] Notarize app (if distributing publicly)
- [ ] Create DMG with proper layout
- [ ] Write user documentation
- [ ] Create download page

## Next Steps

1. **Start with setup wizard** - This is the biggest UX improvement
2. **Test PyInstaller build** - Ensure all dependencies bundle correctly
3. **Create app icon** - Professional appearance matters
4. **Test on clean system** - Verify no external dependencies
5. **Code signing** - Required for distribution

## Alternative: Electron Approach

If PyInstaller proves problematic, consider Electron:
- Wrap FastAPI backend in Electron
- Use Electron's built-in browser
- Better native integration
- Larger bundle size (~100MB+)
- More complex build process

**Recommendation: Try PyInstaller first, fall back to Electron if needed.**

