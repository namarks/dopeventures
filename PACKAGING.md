# Packaging Dopetracks as a macOS App

This document describes how to build Dopetracks as a standalone macOS application that users can download and run without installing Python or editing configuration files.

## Overview

The packaging system uses PyInstaller to bundle:
- Python runtime and all dependencies
- Application code and frontend files
- Setup wizard for first-time configuration

The resulting app bundle (`Dopetracks.app`) can be distributed as a `.dmg` file.

## Prerequisites

- macOS (required for building macOS apps)
- Python 3.11+ with virtual environment set up
- All dependencies installed (`pip install -r requirements.txt`)
- PyInstaller (installed automatically by build script)

## Building the App

### Quick Build

```bash
./build_mac_app.sh
```

This will:
1. Check prerequisites
2. Install PyInstaller if needed
3. Build the app bundle using `build_app.spec`
4. Optionally create a `.dmg` file

### Output

- **App Bundle**: `dist/Dopetracks.app`
- **DMG** (if created): `dist/Dopetracks.dmg`

## Testing the Bundled App

### Local Testing

1. Open the app bundle:
   ```bash
   open dist/Dopetracks.app
   ```

2. First launch will open the setup wizard in your browser
3. Complete the setup (enter Spotify credentials)
4. App will launch automatically after setup

### Testing on Clean System

To verify the app works without external dependencies:

1. Create a new macOS user account (or use a VM)
2. Copy `Dopetracks.app` to the test system
3. Ensure Python is NOT installed (or use a clean system)
4. Launch the app and verify it works

## How It Works

### Launch Flow

1. **First Launch**:
   - `launch_bundled.py` checks for config file
   - If missing, launches setup wizard on port 8889
   - User completes setup in browser
   - Config saved to `~/Library/Application Support/Dopetracks/.env`
   - Main app launches on port 8888

2. **Subsequent Launches**:
   - Config file found
   - Main app launches immediately
   - Browser opens to `http://127.0.0.1:8888`

### File Locations

When running as a bundled app:

- **Config**: `~/Library/Application Support/Dopetracks/.env`
- **Database**: `~/Library/Application Support/Dopetracks/local.db`
- **Logs**: `~/Library/Logs/Dopetracks/backend.log`

### Setup Wizard

The setup wizard is a web-based interface that:
- Guides users through Spotify Developer App creation
- Collects and validates Spotify credentials
- Saves configuration automatically
- Provides clear error messages

## Customization

### App Icon

1. Create an icon file: `resources/icon.icns`
2. Update `build_app.spec`:
   ```python
   icon='resources/icon.icns',
   ```

### App Metadata

Edit `build_app.spec` to change:
- Bundle identifier: `bundle_identifier='com.dopetracks.app'`
- Version: `CFBundleVersion` and `CFBundleShortVersionString`
- Minimum macOS version: `LSMinimumSystemVersion`

### Console Output

For debugging, set `console=True` in `build_app.spec`:
```python
console=True,  # Show terminal window
```

## Code Signing (Optional but Recommended)

To sign the app for distribution:

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  dist/Dopetracks.app
```

You need:
- Apple Developer account
- Developer ID certificate installed in Keychain

## Notarization (Required for Distribution)

For apps distributed outside the Mac App Store, Apple requires notarization:

```bash
# Create DMG first
hdiutil create -volname "Dopetracks" \
  -srcfolder dist/Dopetracks.app \
  -ov -format UDZO dist/Dopetracks.dmg

# Submit for notarization
xcrun notarytool submit dist/Dopetracks.dmg \
  --apple-id your@email.com \
  --team-id YOUR_TEAM_ID \
  --password YOUR_APP_PASSWORD \
  --wait
```

## Troubleshooting

### Build Fails

- **Missing dependencies**: Ensure virtual environment is active and all packages installed
- **PyInstaller errors**: Check `build_app.spec` for correct paths
- **Import errors**: Add missing modules to `hiddenimports` in `build_app.spec`

### App Won't Launch

- **Check logs**: `~/Library/Logs/Dopetracks/launcher.log`
- **Run with console**: Set `console=True` in `build_app.spec` to see errors
- **Check permissions**: Ensure app has Full Disk Access if needed

### Setup Wizard Issues

- **Port conflicts**: Ensure ports 8888 and 8889 are available
- **Browser doesn't open**: Manually navigate to `http://127.0.0.1:8889`
- **Config not saving**: Check write permissions to `~/Library/Application Support/Dopetracks/`

## Development vs Bundled

The app detects if it's running as a bundled app:

- **Bundled**: Uses `sys._MEIPASS` for app files, `~/Library/Application Support/` for user data
- **Development**: Uses project directory structure, `.env` in project root

This allows the same codebase to work in both modes.

## Distribution

### Option 1: Direct Download

1. Host `.dmg` file on website or GitHub Releases
2. Users download and install
3. **Pros**: Full control, no restrictions
4. **Cons**: Users must trust download source

### Option 2: Homebrew Cask

Create a Homebrew formula for easy installation:

```ruby
cask 'dopetracks' do
  version '1.0.0'
  sha256 '...'
  
  url "https://github.com/yourusername/dopeventures/releases/download/v#{version}/Dopetracks.dmg"
  name 'Dopetracks'
  homepage 'https://github.com/yourusername/dopeventures'
  
  app 'Dopetracks.app'
end
```

### Option 3: Mac App Store

- Requires sandboxing (may conflict with Messages DB access)
- Apple review process
- Revenue share

## Next Steps

- [ ] Create app icon (`.icns` file)
- [ ] Test on clean macOS system
- [ ] Code sign app bundle
- [ ] Notarize for distribution
- [ ] Create download page
- [ ] Set up automated builds (GitHub Actions)

## See Also

- [Packaging Strategy](./PACKAGING_STRATEGY.md) - Detailed implementation plan
- [PyInstaller Documentation](https://pyinstaller.org/)
- [Apple Code Signing Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)

