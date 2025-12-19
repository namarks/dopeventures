# Dopetracks Native macOS App (Swift + SwiftUI)

This is the native Swift/SwiftUI implementation of Dopetracks for macOS.

## Architecture

- **Frontend**: SwiftUI native macOS app
- **Backend**: FastAPI (Python) running as local server on `localhost:8888`
- **Communication**: HTTP REST API

## Project Structure

```
DopetracksApp/
├── DopetracksApp/
│   ├── DopetracksApp.swift          # App entry point
│   ├── ContentView.swift            # Main view with navigation
│   ├── Models/                       # Data models
│   │   ├── Chat.swift
│   │   ├── Playlist.swift
│   │   ├── Message.swift
│   │   └── SpotifyProfile.swift
│   ├── Services/                     # Business logic
│   │   ├── APIClient.swift          # HTTP client for FastAPI
│   │   └── BackendManager.swift     # Python backend process manager
│   └── Views/                        # SwiftUI views
│       ├── ChatListView.swift
│       ├── PlaylistCreationView.swift
│       ├── PlaylistListView.swift
│       └── SettingsView.swift
└── README.md
```

## Setup

### Prerequisites

- macOS 12.0+ (for SwiftUI)
- Xcode 14.0+
- Python backend running (or bundled)

### Development Setup

1. **Open in Xcode**:
   ```bash
   open DopetracksApp/DopetracksApp.xcodeproj
   ```

2. **Configure Backend**:
   - For development: Ensure Python backend is running on `localhost:8888`
   - For production: Backend will be bundled and launched automatically

3. **Build and Run**:
   - Select "DopetracksApp" scheme
   - Press Cmd+R to build and run

## Building for Distribution

### Option 1: Bundle Python Backend

1. Build Python backend with PyInstaller:
   ```bash
   ./build/build_mac_app.sh
   ```

2. Copy backend executable to Xcode project:
   ```bash
   cp -R dist/Dopetracks.app/Contents/MacOS/Dopetracks \
        DopetracksApp/DopetracksApp/Resources/Backend/
   ```

3. Update `BackendManager.swift` to use bundled executable path

4. Build Swift app in Xcode (Product → Archive)

### Option 2: Separate Backend Service

- Backend runs as separate process/service
- Swift app connects to existing backend
- Simpler distribution but requires backend setup

## Features

- ✅ Native macOS UI with SwiftUI
- ✅ Chat search and selection
- ✅ Playlist creation with date filtering
- ✅ Spotify profile integration
- ✅ Automatic backend process management
- ✅ Health checking and error handling

## API Integration

The app communicates with the FastAPI backend via HTTP:

- `GET /health` - Health check
- `GET /chat-search-optimized` - Search chats
- `GET /chat/{id}/recent-messages` - Get messages
- `POST /create-playlist-optimized-stream` - Create playlist
- `GET /user-profile` - Get Spotify profile
- `GET /user-playlists` - List playlists

See `APIClient.swift` for implementation details.

## Next Steps

- [ ] Create Xcode project file (`.xcodeproj`)
- [ ] Add app icon and assets
- [ ] Implement Server-Sent Events for progress updates
- [ ] Add native notifications
- [ ] System tray integration
- [ ] Code signing and notarization
- [ ] DMG packaging

