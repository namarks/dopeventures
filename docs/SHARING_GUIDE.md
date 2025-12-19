# Sharing Dopetracks with Friends

This guide explains how to share the Dopetracks app with others.

## Quick Share (Easiest Method)

### Step 1: Locate the DMG File

The packaged app is located at:
```
dist/Dopetracks.dmg
```

### Step 2: Share the DMG File

You can share the DMG file through:

- **AirDrop** (if friend is nearby): Right-click `Dopetracks.dmg` → Share → AirDrop
- **Cloud Storage**: Upload to Dropbox, Google Drive, iCloud, or similar
- **File Transfer**: Email (if under size limit) or use a file transfer service
- **GitHub Releases**: If your repo is public, create a release and attach the DMG

### Step 3: Tell Your Friend What to Do

Send your friend these instructions:

---

## Instructions for Your Friend

### Prerequisites

Your friend needs:
- **macOS** (the app only works on Mac)
- **Spotify Premium account** (required for playlist creation)
- **Spotify Developer App** (free, takes 2 minutes to set up)

### Installation Steps

1. **Download the DMG file** you received

2. **Open the DMG**: Double-click `Dopetracks.dmg`

3. **Install the app**: 
   - Drag `Dopetracks.app` to the Applications folder
   - If macOS warns about an unidentified developer, right-click the app → Open → Click "Open" in the dialog

4. **Launch the app**: 
   - Open Applications folder
   - Double-click `Dopetracks.app`
   - First launch will open a setup wizard in your browser

5. **Complete Setup**:
   - The setup wizard will guide them through creating a Spotify Developer App
   - They'll need to:
     - Go to https://developer.spotify.com/dashboard
     - Create a new app
     - Copy the Client ID and Client Secret
     - Add redirect URI: `http://127.0.0.1:8888/callback`
     - Paste credentials into the setup wizard
   - The wizard will save everything automatically

6. **Start using the app**: After setup, the app will launch automatically!

---

## Rebuilding the App (If Needed)

If you need to rebuild the app with the latest changes:

```bash
./build/build_mac_app.sh
```

This will:
1. Build a fresh `Dopetracks.app` bundle
2. Optionally create a new `Dopetracks.dmg` file

The output will be in `dist/Dopetracks.dmg`.

---

## Code Signing & Notarization (Optional but Recommended)

For wider distribution, you may want to code sign and notarize the app so users don't see security warnings.

### Code Signing

```bash
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name" \
  dist/Dopetracks.app
```

**Requirements:**
- Apple Developer account ($99/year)
- Developer ID certificate installed in Keychain

### Notarization

```bash
# Submit for notarization
xcrun notarytool submit dist/Dopetracks.dmg \
  --apple-id your@email.com \
  --team-id YOUR_TEAM_ID \
  --password YOUR_APP_PASSWORD \
  --wait
```

**Note:** Notarization is required if distributing outside the Mac App Store, but not required for sharing with friends.

---

## Sharing via GitHub Releases

If your repository is on GitHub:

1. **Create a release**:
   - Go to your repo → Releases → "Create a new release"
   - Tag version (e.g., `v1.0.0`)
   - Add release notes

2. **Attach the DMG**:
   - Drag `dist/Dopetracks.dmg` to the "Attach binaries" section
   - Publish the release

3. **Share the release URL** with your friend

---

## Troubleshooting for Your Friend

### "App can't be opened because it is from an unidentified developer"

**Solution:**
1. Right-click `Dopetracks.app`
2. Select "Open"
3. Click "Open" in the security dialog

Or:
1. System Settings → Privacy & Security
2. Scroll to "Security" section
3. Click "Open Anyway" next to the warning

### "Setup wizard doesn't open"

**Solution:**
- Manually open: http://127.0.0.1:8889

### "Spotify authorization fails"

**Solution:**
- Make sure redirect URI in Spotify Developer Dashboard is exactly: `http://127.0.0.1:8888/callback`
- Not `localhost` - must be `127.0.0.1`

### "Permission denied" when accessing Messages

**Solution:**
1. System Settings → Privacy & Security → Full Disk Access
2. Add `Dopetracks.app` to the list
3. Restart the app

---

## File Size Considerations

The DMG file is typically **50-150 MB** depending on dependencies. If sharing via email:
- Most email providers limit attachments to 25-50 MB
- Use cloud storage or file transfer services for larger files

---

## Summary

**Easiest way to share:**
1. Find `dist/Dopetracks.dmg`
2. Upload to cloud storage or use AirDrop
3. Send your friend the link/file
4. Tell them to drag the app to Applications and launch it

That's it! The setup wizard handles everything else.

