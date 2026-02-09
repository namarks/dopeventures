# Dopetracks

A macOS desktop app that creates Spotify playlists from songs shared in your iMessage group chats.

All data stays on your Mac. The app reads your local Messages database, finds Spotify links, and builds playlists from them.

## Quick Start

### Users (Packaged App)

1. Download the `.dmg` from [Releases](https://github.com/namarks/dopeventures/releases)
2. Drag to Applications, open, follow the setup wizard
3. See the [User Guide](USER_GUIDE.md) for details

### Developers

```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures
./setup.sh             # Creates venv, installs deps, creates .env
# Edit .env with your Spotify credentials (see docs/SPOTIFY_OAUTH_SETUP.md)
python3 dev_server.py  # Starts backend at http://127.0.0.1:8888
```

For the Swift frontend, open `DopetracksApp/DopetracksApp.xcodeproj` in Xcode.

See [QUICK_START.md](QUICK_START.md) for the full developer walkthrough.

## Prerequisites

- macOS (required for iMessage access)
- Spotify account + [developer app credentials](docs/SPOTIFY_OAUTH_SETUP.md)
- Full Disk Access (System Settings > Privacy & Security)
- Python 3.11+ and Xcode 15+ (for development only)

## How It Works

1. Reads `~/Library/Messages/chat.db` (local iMessage database, read-only)
2. Extracts Spotify links from chat messages
3. Authenticates with Spotify via OAuth
4. Creates or updates playlists with the found tracks

## Documentation

| Doc | Audience | Description |
|-----|----------|-------------|
| [User Guide](USER_GUIDE.md) | Users | Setup, usage, troubleshooting |
| [Quick Start](QUICK_START.md) | Developers | 5-minute dev environment setup |
| [Project Overview](PROJECT_OVERVIEW.md) | Developers | Architecture and technical reference |
| [docs/](docs/INDEX.md) | Developers | Testing, packaging, Spotify setup, troubleshooting |

## Security & Privacy

- **Local only** -- no data leaves your Mac
- Messages database is read-only
- Spotify tokens stored locally in `~/.dopetracks/local.db`
- No analytics, no telemetry, no user accounts

## License

MIT
