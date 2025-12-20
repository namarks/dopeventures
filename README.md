# Dopetracks

Create Spotify playlists from songs shared in your iMessage chats.

## 🎯 Quick Navigation

**Are you a user who just wants to use Dopetracks?**
- → **[USER_GUIDE.md](./USER_GUIDE.md)** - Complete guide for end users (download, setup, usage)
- → **[QUICK_START.md](./QUICK_START.md)** - Get running in 5 minutes

**Are you a developer contributing to or modifying Dopetracks?**
- → **[docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md)** - Development setup and architecture
- → **[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)** - Technical architecture and design

## What is Dopetracks?

Dopetracks automatically creates Spotify playlists from songs your friends have shared in iMessage chats. It:

1. Extracts messages from your Messages database (`~/Library/Messages/chat.db`)
2. Finds messages containing Spotify links
3. Creates a Spotify playlist with all the identified songs

## Prerequisites

- **macOS** (required for Messages database access)
- **Spotify Premium account** (required for playlist creation)
- **Spotify Developer App** (free, 2-minute setup)

**For Developer Setup:**
- **Python 3.11+**

## Quick Start (5 Minutes)

### Option 1: Packaged macOS App (Easiest - Coming Soon!)

Download the `.dmg` file, drag to Applications, and launch. No Python installation required!

See **[docs/PACKAGING.md](./docs/PACKAGING.md)** for building the app yourself.

### Option 2: Developer Setup (Command Line)

```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures
./setup.sh
# Edit .env file with Spotify credentials
python3 dev_server.py
```

See **[QUICK_START.md](./QUICK_START.md)** for step-by-step instructions.

## Documentation Structure

### For Users
- **[USER_GUIDE.md](./USER_GUIDE.md)** - Complete user guide (download, setup, usage, troubleshooting)
- **[QUICK_START.md](./QUICK_START.md)** - Quick reference for getting started

### For Developers
- **[docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md)** - Development environment setup
- **[PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)** - Architecture, database schema, technical details
- **[docs/](./docs/)** - Additional technical documentation

## Features

- ✅ **Local-first** - All data stays on your Mac, nothing uploaded
- ✅ **Automatic chat detection** - Finds your Messages database automatically
- ✅ **Spotify OAuth** - Secure authentication with Spotify
- ✅ **Streaming playlist creation** - Real-time progress updates
- ✅ **Contact photos** - Displays contact photos from AddressBook
- ✅ **Date range filtering** - Create playlists from specific time periods
- ✅ **Multiple chat support** - Combine songs from multiple chats

## Security & Privacy

- ✅ **All data stays local** - Nothing is uploaded to external servers
- ✅ **Open source** - You can review all the code
- ✅ **No tracking** - The app doesn't collect any analytics
- ✅ **Secure credentials** - Spotify tokens stored locally and encrypted

## Troubleshooting

Common issues and solutions:

- **"Permission denied" for Messages** - Grant Full Disk Access in System Preferences
- **"Spotify authorization fails"** - Check redirect URI uses `127.0.0.1` (not `localhost`)
- **"Port already in use"** - Kill existing process: `pkill -f uvicorn`

**For Developer Setup:**
- **"No module named 'httpx'"** - Run `pip install -r requirements.txt` in your virtual environment

For more help, see:
- **[USER_GUIDE.md](./USER_GUIDE.md)** - User troubleshooting section
- **[docs/TROUBLESHOOTING.md](./docs/TROUBLESHOOTING.md)** - Detailed troubleshooting guide

## Contributing

See **[docs/DEVELOPER_GUIDE.md](./docs/DEVELOPER_GUIDE.md)** for development setup and contribution guidelines.

## License

See [packages/dopetracks/LICENSE](./packages/dopetracks/LICENSE) for license information.

## Useful Resources

- [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
