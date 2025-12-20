# Native macOS App

This document describes the native macOS app architecture and development.

## Current Architecture

- **Backend**: FastAPI (Python) - API server running on `http://127.0.0.1:8888`
- **Frontend**: SwiftUI native macOS application
- **Launch**: Swift app launches Python backend automatically
- **Communication**: Swift app communicates with backend via HTTP REST API

## Swift App Structure

- **`DopetracksApp/DopetracksApp/`**: Main Swift app code
  - **`Models/`**: Data models (Chat, Message, Playlist, SpotifyProfile)
  - **`Services/`**: 
    - `APIClient.swift`: HTTP client for backend API
    - `BackendManager.swift`: Manages Python backend process lifecycle
  - **`Views/`**: SwiftUI views
    - `ContentView.swift`: Main app view
    - `ChatListView.swift`: List of chats
    - `PlaylistCreationView.swift`: Playlist creation interface
    - `PlaylistListView.swift`: List of created playlists
    - `SettingsView.swift`: App settings

## Backend Launch

The Swift app automatically launches the Python backend when it starts:

1. `BackendManager.swift` checks if backend is already running
2. If not, it launches `dev_server.py` (development) or `app_launcher.py` (production)
3. Backend runs on `http://127.0.0.1:8888`
4. Swift app connects to backend via `APIClient.swift`

## Development

### Running in Development Mode

1. Start backend manually (optional, Swift app can start it):
   ```bash
   python dev_server.py
   ```

2. Open Swift app in Xcode:
   ```bash
   open DopetracksApp/DopetracksApp.xcodeproj
   ```

3. Build and run from Xcode

### Backend API

The backend provides REST API endpoints:
- `GET /health` - Health check
- `GET /chats` - List chats
- `GET /chats/{chat_id}/messages` - Get messages for a chat
- `POST /playlists` - Create playlist
- `GET /playlists` - List playlists
- `POST /fts/index` - Index messages for full-text search
- `GET /fts/status` - Get FTS index status

See `/docs` endpoint for full API documentation when backend is running.

## Permissions

The app requires Full Disk Access to read the Messages database:
- Location: `~/Library/Messages/chat.db`
- The Swift app should prompt for this permission on first launch
- Users can also grant it manually in System Settings > Privacy & Security > Full Disk Access

## Building for Distribution

See `docs/PACKAGING.md` for instructions on building a distributable app bundle.
