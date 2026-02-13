# Dopetracks

Local-first macOS desktop app. Creates Spotify playlists from songs shared in iMessage group chats. **Not a web app** — no server deployment, no user accounts, no cloud storage.

## Architecture

- **Swift/SwiftUI frontend** (`DopetracksApp/App/`) — native macOS app
- **Python FastAPI backend** (`packages/dopetracks/`) — runs locally on `http://127.0.0.1:8888`
- The Swift app spawns and manages the Python backend process via `BackendManager.swift`
- Single-user, no authentication. All data stays on the user's Mac.

## Key Paths

| What | Where |
|------|-------|
| Backend entry point | `packages/dopetracks/app.py` (thin shell — routes in `routes/`) |
| Config | `packages/dopetracks/config.py` (loads `.env`) |
| Database models | `packages/dopetracks/database/models.py` |
| iMessage processing | `packages/dopetracks/processing/imessage_data_processing/` |
| Spotify integration | `packages/dopetracks/processing/spotify_interaction/` |
| Swift app code | `DopetracksApp/App/` (Models, Views, ViewModels, Services) |
| Dev server | `dev_server.py` |
| Tests | `packages/dopetracks/tests/` |

## Development

```bash
./setup.sh                  # venv + deps + .env template
python3 dev_server.py       # backend at 127.0.0.1:8888
python -m pytest packages/dopetracks/tests/ -v  # run tests
```

Swift frontend: open `DopetracksApp/DopetracksApp.xcodeproj` in Xcode.

## Data Stores

- **App database:** `~/.dopetracks/local.db` (SQLite — Spotify tokens)
- **Spotify cache:** `~/.spotify_cache/spotify_cache.db` (track metadata)
- **Messages source:** `~/Library/Messages/chat.db` (read-only)

## Conventions

- Backend runs on port 8888, no other ports
- Redirect URI must use `127.0.0.1`, never `localhost` (Spotify requirement)
- SQLite only — no PostgreSQL, Redis, or cloud databases
- No web deployment files (no Procfile, no Dockerfile, no runtime.txt)
- No user authentication system (no passwords, sessions, or JWTs)

## Known Technical Debt

- 3 pre-existing ingestion tests fail (need macOS Messages DB schema in test fixture)
- `app.py` route split is complete but `routes/helpers.py` is 386 lines — could be further decomposed
- Some code duplication remains in processing modules (timestamp conversion, DB connection patterns)

## Planning & Context

Planning docs, braindumps, and research live in the Second Brain:
`~/Documents/SecondBrain/04-projects/imessage-spotify-app/`

Check there for:
- Feature ideas and braindumps (`braindumps/`)
- Competitive analysis (`competitive/`)
- Architecture decisions and specs (`planning/`)
