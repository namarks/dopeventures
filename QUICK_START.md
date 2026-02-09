# Quick Start (Developer Setup)

Get Dopetracks running from source in 5 minutes.

> **End users**: Download the packaged app instead -- see [USER_GUIDE.md](USER_GUIDE.md)

## Prerequisites

- macOS, Python 3.11+, Xcode 15+
- Spotify account + [Developer App](docs/SPOTIFY_OAUTH_SETUP.md)

## 1. Clone and Install

```bash
git clone https://github.com/namarks/dopeventures.git
cd dopeventures
./setup.sh   # creates venv, installs deps, creates .env template
```

## 2. Configure Spotify

Edit `.env` with your credentials:

```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

Get these from [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) -- see [docs/SPOTIFY_OAUTH_SETUP.md](docs/SPOTIFY_OAUTH_SETUP.md) for details.

## 3. Grant Full Disk Access

System Settings > Privacy & Security > Full Disk Access -- add Terminal (or your Python binary).

## 4. Run the Backend

```bash
source venv/bin/activate
python3 dev_server.py
```

You should see:
```
Starting Dopetracks Application...
Health check: http://127.0.0.1:8888/health
Application: http://127.0.0.1:8888
```

API docs available at http://127.0.0.1:8888/docs

## 5. Run the Swift Frontend

Open `DopetracksApp/DopetracksApp.xcodeproj` in Xcode and run. The Swift app will connect to the backend automatically.

## 6. Use the App

1. Authorize Spotify (one-time OAuth flow)
2. Search for chats by name or participant
3. Select chats, set a date range, create your playlist

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |
| Permission denied for Messages | Grant Full Disk Access (step 3) |
| Spotify auth fails | Redirect URI must use `127.0.0.1`, not `localhost` |
| Port 8888 in use | `pkill -f uvicorn` or set `DOPETRACKS_KILL_PORT=1` |

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for more.
