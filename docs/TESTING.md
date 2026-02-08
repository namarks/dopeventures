# Testing Guide

Dopetracks is a local-first macOS desktop app. The Python backend runs on
`http://127.0.0.1:8888` and serves both the API and the Swagger UI. There is no
user authentication -- the app operates as a single-user local service.

---

## Quick Start

1. Activate the virtual environment and start the dev server:

   ```bash
   source venv/bin/activate
   python dev_server.py
   ```

   The server binds to `127.0.0.1:8888` with auto-reload enabled.

2. Open the interactive API docs (Swagger UI) in a browser:

   ```
   http://127.0.0.1:8888/docs
   ```

   You can execute every endpoint directly from this page.

### Prerequisites

- **Full Disk Access** must be granted to your terminal (or the Python
  binary) so the backend can read `~/Library/Messages/chat.db`.
- A `.env` file at the project root with valid `SPOTIFY_CLIENT_ID`,
  `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REDIRECT_URI` (must use
  `127.0.0.1`, not `localhost`).

### Port Conflict

If port 8888 is already in use:

```bash
lsof -ti:8888 | xargs kill -9
```

Or set `DOPETRACKS_KILL_PORT=1` before running `dev_server.py` to auto-kill
the existing process.

---

## Testing Checklist

### 1. Health Check

Verify the server is running and can see the Messages database.

```bash
curl http://127.0.0.1:8888/health
```

Expected response:

```json
{
  "status": "healthy",
  "database": "connected",
  "messages_db": "found",
  "messages_db_path": "/Users/<you>/Library/Messages/chat.db",
  "environment": "local",
  "version": "3.0.0-local"
}
```

If `messages_db` is `"not_found"`, grant Full Disk Access and restart.

### 2. Spotify Authorization

Spotify OAuth is required before any playlist or profile endpoint will work.

1. Get the client ID and redirect URI:

   ```bash
   curl http://127.0.0.1:8888/get-client-id
   ```

2. Open the Spotify authorize URL in a browser (constructed from the
   client ID and redirect URI returned above). After granting access,
   Spotify redirects to `/callback`, which exchanges the code for tokens
   and stores them in `~/.dopetracks/local.db`.

3. Confirm tokens are working:

   ```bash
   curl http://127.0.0.1:8888/user-profile
   ```

   Should return your Spotify display name, email, and profile image.

### 3. Chat Search

List all chats:

```bash
curl http://127.0.0.1:8888/chats
```

Search by name:

```bash
curl "http://127.0.0.1:8888/chat-search-optimized?query=Family"
```

Advanced search with date range and message content:

```bash
curl "http://127.0.0.1:8888/chat-search-advanced?query=Music&start_date=2024-01-01&end_date=2025-01-01&message_content=spotify"
```

View recent messages for a specific chat (replace `3` with a real chat ID):

```bash
curl "http://127.0.0.1:8888/chat/3/recent-messages?limit=10"
```

### 4. Playlist Creation

Create a playlist from selected chats. The endpoint streams Server-Sent
Events (SSE) with progress updates.

Using JSON (as the macOS app does):

```bash
curl -N -X POST http://127.0.0.1:8888/create-playlist-optimized-stream \
  -H "Content-Type: application/json" \
  -d '{
    "playlist_name": "Test Playlist",
    "start_date": "2024-01-01T00:00:00+00:00",
    "end_date": "2025-01-01T00:00:00+00:00",
    "chat_ids": [3, 7]
  }'
```

Using form data:

```bash
curl -N -X POST http://127.0.0.1:8888/create-playlist-optimized-stream \
  -F "playlist_name=Test Playlist" \
  -F "start_date=2024-01-01T00:00:00+00:00" \
  -F "end_date=2025-01-01T00:00:00+00:00" \
  -F "selected_chat_ids=[3,7]"
```

The `-N` flag disables output buffering so you see SSE events in real time.
Events include `progress` updates (with stage and percentage) and a final
`complete` or `error` event.

---

## API Endpoints Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API info (name, version, links) |
| GET | `/health` | Health check -- database and Messages DB status |
| GET | `/docs` | Swagger UI (interactive API explorer) |
| GET | `/prepared-status` | Staleness info for the prepared messages DB |
| GET | `/get-client-id` | Spotify client ID and redirect URI for OAuth |
| GET | `/callback` | Spotify OAuth callback (browser redirect target) |
| GET | `/user-profile` | Spotify profile of the authorized user |
| GET | `/user-playlists` | Spotify playlists of the authorized user |
| GET | `/chats` | All chats with statistics |
| GET | `/chat-search-optimized` | Search chats by name (`?query=`) |
| GET | `/chat-search-prepared` | Search prepared messages DB (name, date, content filters) |
| GET | `/chat-search-advanced` | Advanced multi-filter search, optional streaming (`?stream=true`) |
| POST | `/create-playlist-optimized-stream` | Create Spotify playlist (SSE progress stream) |
| GET | `/chat/{chat_id}/recent-messages` | Recent messages for a chat |
| GET | `/contact-photo/{unique_id}` | Contact photo by unique ID |
| POST | `/fts/index` | Build or rebuild the full-text search index |
| GET | `/fts/status` | Full-text search index status |
| GET | `/validate-username` | Check if Messages DB exists for a macOS username |
| GET | `/open-full-disk-access` | Open macOS System Settings to Full Disk Access |

---

## Running Automated Tests (pytest)

Tests live under `packages/dopetracks/tests/`. Run them from the project root:

```bash
source venv/bin/activate
python -m pytest packages/dopetracks/tests/ -v
```

To run a specific test file:

```bash
python -m pytest packages/dopetracks/tests/processing/imessage_data_processing/test_ingestion_prepared.py -v
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `messages_db: "not_found"` in health check | Grant Full Disk Access to Terminal / Python in System Settings > Privacy & Security > Full Disk Access, then restart the server. |
| `Spotify not authorized` (401) | Complete the OAuth flow described in the Spotify Authorization section above. Tokens persist in `~/.dopetracks/local.db`. |
| Port 8888 already in use | `lsof -ti:8888 \| xargs kill -9` or set `DOPETRACKS_KILL_PORT=1`. |
| `SPOTIFY_REDIRECT_URI contains 'localhost'` | Edit `.env` and change `localhost` to `127.0.0.1`. Spotify rejects localhost. |
