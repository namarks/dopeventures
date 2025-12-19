# Creating GitHub Releases

This guide explains how to create GitHub Releases for distributing the Dopetracks DMG file.

## Quick Start: Manual Release

### Step 1: Build the DMG

```bash
# Make sure you're in the project root
cd /path/to/dopeventures

# Build the app and create DMG
./build/build_mac_app.sh
# When prompted, type 'y' to create DMG

# Or create DMG manually:
DMG_DIR="dist/dmg"
rm -rf "$DMG_DIR"
mkdir -p "$DMG_DIR"
cp -R "dist/Dopetracks.app" "$DMG_DIR/"
hdiutil create -volname "Dopetracks" \
  -srcfolder "$DMG_DIR" \
  -ov -format UDZO \
  "dist/Dopetracks.dmg"
```

### Step 2: Create Release on GitHub

1. **Go to your repository**: https://github.com/namarks/dopeventures
2. **Click "Releases"** (on the right sidebar, or go to `/releases`)
3. **Click "Draft a new release"** or **"Create a new release"**
4. **Fill in the release form**:
   - **Choose a tag**: Click "Choose a tag" and create a new tag (e.g., `v1.0.0`)
   - **Release title**: `v1.0.0 - Initial Release` (or descriptive title)
   - **Description**: Add release notes, what's new, known issues, etc.
   - **Attach binaries**: 
     - **Option 1**: Click "Attach binaries by selecting files" and browse to `dist/Dopetracks.dmg`
     - **Option 2**: Drag `dist/Dopetracks.dmg` into the "Attach binaries" section
     - **Note**: If drag-and-drop doesn't work, use the file picker button
5. **Click "Publish release"**

### Step 3: Verify

- Visit: https://github.com/namarks/dopeventures/releases/latest
- You should see your release with the DMG file available for download
- Users can now download from this page

## Alternative: Using GitHub CLI (Recommended)

If the web interface has issues with .dmg files, use GitHub CLI:

### Install GitHub CLI

```bash
# macOS
brew install gh

# Or download from: https://cli.github.com/
```

### Authenticate

```bash
gh auth login
```

### Create Release with DMG

```bash
# 1. Create and push a tag first
git tag v1.0.0
git push origin v1.0.0

# 2. Create release and attach DMG
gh release create v1.0.0 \
  --title "v1.0.0 - Initial Release" \
  --notes "Initial release of Dopetracks" \
  dist/Dopetracks.dmg

# Or if release already exists, upload the file:
gh release upload v1.0.0 dist/Dopetracks.dmg
```

This method is more reliable for binary files!

## Automated Releases (GitHub Actions)

If you want automated releases, a GitHub Actions workflow is set up in `.github/workflows/release.yml`.

### How It Works

1. **Create and push a version tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **GitHub Actions automatically**:
   - Builds the app on macOS
   - Creates the DMG file
   - Creates a GitHub Release
   - Attaches the DMG to the release

### Creating a Release with Automation

```bash
# 1. Make sure all changes are committed
git add -A
git commit -m "Prepare for v1.0.0 release"

# 2. Create and push the tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# 3. GitHub Actions will automatically:
#    - Build the app
#    - Create the release
#    - Attach the DMG
```

### Viewing the Workflow

- Go to: https://github.com/namarks/dopeventures/actions
- You'll see the "Build and Release" workflow running
- Once complete, check the Releases page for your new release

## Release Notes Template

Here's a template for release notes:

```markdown
## What's New

- Feature 1 description
- Feature 2 description
- Bug fixes

## Installation

1. Download `Dopetracks.dmg` from the assets below
2. Open the DMG file
3. Drag `Dopetracks.app` to Applications
4. Launch and follow the setup wizard

## Requirements

- macOS 10.15 or later
- Spotify Premium account
- Spotify Developer App (free, setup wizard will guide you)

## Known Issues

- List any known issues here

## Support

If you encounter issues, please open an issue on GitHub.
```

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **Major** (v2.0.0): Breaking changes
- **Minor** (v1.1.0): New features, backward compatible
- **Patch** (v1.0.1): Bug fixes

## Best Practices

1. **Test the DMG before releasing**: Download and test on a clean system
2. **Write clear release notes**: Help users understand what's new
3. **Tag consistently**: Use version tags (v1.0.0, v1.1.0, etc.)
4. **Mark pre-releases**: Use "Set as a pre-release" for beta versions
5. **Keep old releases**: Don't delete old releases, users may need them

## Troubleshooting

### "Workflow failed to build"
- Check the Actions tab for error messages
- Ensure all dependencies are in `requirements.txt`
- Verify `build/build_mac_app.sh` works locally

### "DMG not attached to release"
- Check the workflow logs
- Verify the DMG was created successfully
- Manually attach if automation fails

### "Can't attach .dmg file in web interface"
- **Use the file picker button** instead of drag-and-drop
- **Use GitHub CLI** (recommended): `gh release create v1.0.0 --title "v1.0.0" dist/Dopetracks.dmg`
- **Try a different browser** (Chrome, Firefox, Safari)
- **Check file size**: GitHub supports files up to 2GB, your DMG is 48MB (well within limits)
- **Verify file exists**: Make sure `dist/Dopetracks.dmg` was created successfully

### "Users can't download"
- Check file size (GitHub has limits - max 2GB per file)
- Verify the release is published (not draft)
- Check repository visibility (public repos allow public downloads)
- Verify the file was actually attached (check the Assets section)

