# Swift Native App Setup Guide

## What's Been Created

The Swift + SwiftUI native macOS app structure has been created on the `swift-native-app` branch. This includes:

### Core Files
- **DopetracksApp.swift** - Main app entry point
- **ContentView.swift** - Root view with tab navigation
- **APIClient.swift** - HTTP client for FastAPI backend
- **BackendManager.swift** - Python backend process manager

### Models
- **Chat.swift** - Chat data model
- **Playlist.swift** - Playlist data model
- **Message.swift** - Message data model
- **SpotifyProfile.swift** - Spotify user profile model

### Views
- **ChatListView.swift** - Chat search and selection
- **PlaylistCreationView.swift** - Create playlists from chats
- **PlaylistListView.swift** - View created playlists
- **SettingsView.swift** - Settings and Spotify profile

## Next Steps

### 1. Create Xcode Project

You need to create an Xcode project to build and run the app:

1. **Open Xcode**
2. **File → New → Project**
3. **macOS → App**
4. **Product Name**: `DopetracksApp`
5. **Interface**: SwiftUI
6. **Language**: Swift
7. **Save location**: `/Users/nmarks/root_code_repo/dopeventures/DopetracksApp/`

8. **Add existing files**:
   - Drag all files from `DopetracksApp/DopetracksApp/` into the Xcode project
   - Make sure "Copy items if needed" is unchecked (files are already in place)
   - Add to target: `DopetracksApp`

### 2. Configure Build Settings

1. **Minimum macOS Version**: 12.0 (for SwiftUI)
2. **Bundle Identifier**: `com.dopetracks.app`
3. **Development Team**: Your Apple Developer account (if code signing)

### 3. Test Backend Connection

For development, you can test with the existing Python backend:

1. Start the Python backend:
   ```bash
   python start.py
   # or
   uvicorn packages.dopetracks.app:app --host 127.0.0.1 --port 8888
   ```

2. Run the Swift app in Xcode
3. The app should connect to `localhost:8888`

### 4. Bundle Backend for Production

For a standalone app, you need to bundle the Python backend:

1. Build Python backend:
   ```bash
   ./build/build_mac_app.sh
   ```

2. Copy backend executable to Xcode project:
   ```bash
   mkdir -p DopetracksApp/DopetracksApp/Resources/Backend
   cp dist/Dopetracks.app/Contents/MacOS/Dopetracks \
      DopetracksApp/DopetracksApp/Resources/Backend/
   ```

3. Update `BackendManager.swift` to use the bundled path:
   ```swift
   private var backendExecutablePath: URL? {
       guard let bundlePath = Bundle.main.resourcePath else { return nil }
       let executable = URL(fileURLWithPath: bundlePath)
           .appendingPathComponent("Backend")
           .appendingPathComponent("Dopetracks")
       return FileManager.default.fileExists(atPath: executable.path) ? executable : nil
   }
   ```

4. Add backend to Xcode project:
   - Right-click `Resources` folder
   - Add Files to "DopetracksApp"
   - Select `Backend/Dopetracks`
   - Check "Copy items if needed"
   - Add to target: `DopetracksApp`

### 5. Add App Icon

1. Create app icon set in Xcode:
   - Right-click `Assets.xcassets`
   - New Image Set → Name it "AppIcon"
   - Add icon images (512x512, 256x256, etc.)

2. Or use an icon generator tool

### 6. Code Signing & Distribution

1. **Code Signing**:
   - Select project in Xcode
   - Signing & Capabilities
   - Select your development team
   - Enable "Automatically manage signing"

2. **Notarization** (for distribution):
   - Archive the app (Product → Archive)
   - Export for distribution
   - Notarize with Apple

3. **Create DMG**:
   ```bash
   hdiutil create -volname "Dopetracks" \
     -srcfolder "DopetracksApp.app" \
     -ov -format UDZO "Dopetracks.dmg"
   ```

## Development Workflow

1. **Backend Development**: Continue using Python/FastAPI
2. **Frontend Development**: Use Xcode for SwiftUI
3. **Testing**: Run both simultaneously (backend on 8888, Swift app connects)

## API Endpoints Used

The Swift app communicates with these FastAPI endpoints:

- `GET /health` - Health check
- `GET /get-client-id` - Get Spotify client ID
- `GET /chat-search-optimized?query=...` - Search chats
- `GET /chat/{id}/recent-messages` - Get messages
- `POST /create-playlist-optimized-stream` - Create playlist
- `GET /user-profile` - Get Spotify profile
- `GET /user-playlists` - List playlists

## Troubleshooting

### Backend won't start
- Check that Python backend is running on port 8888
- Verify `BackendManager.swift` has correct path
- Check logs in Xcode console

### API calls fail
- Verify backend is running: `curl http://127.0.0.1:8888/health`
- Check CORS settings in FastAPI (should allow localhost)
- Verify API endpoint URLs in `APIClient.swift`

### Build errors
- Ensure minimum macOS version is 12.0+
- Check that all Swift files are added to target
- Verify imports are correct

## Resources

- [SwiftUI Documentation](https://developer.apple.com/documentation/swiftui/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/macos)

