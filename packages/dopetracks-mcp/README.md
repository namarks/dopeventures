# Dopetracks MCP Server

A Model Context Protocol (MCP) server that enables natural language playlist creation from iMessage conversations via Claude Code.

## Features

- **Search iMessage chats** - Find conversations by name or participant
- **Extract Spotify links** - Get all Spotify URLs from a chat within a date range
- **Create playlists** - Build Spotify playlists from extracted links
- **Get sharing stats** - See who shared the most songs, unique track counts, etc.

## Prerequisites

1. **macOS** - Requires access to the Messages database
2. **Full Disk Access** - Grant to your terminal app in System Preferences > Security & Privacy > Privacy
3. **Spotify Developer Account** - Get credentials from https://developer.spotify.com/dashboard

## Installation

```bash
cd packages/dopetracks-mcp
pip install -e .
```

## Configuration

### 1. Set Spotify Credentials

Create or update `.env` in the project root:

```bash
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

### 2. Add to Claude Code MCP Servers

Add to `~/.claude/mcp_servers.json`:

```json
{
  "dopetracks": {
    "command": "python",
    "args": ["-m", "dopetracks_mcp.server"],
    "cwd": "/path/to/dopeventures/packages/dopetracks-mcp"
  }
}
```

Or using the installed script:

```json
{
  "dopetracks": {
    "command": "dopetracks-mcp"
  }
}
```

## Usage

Once configured, use natural language with Claude Code:

```
You: Create a playlist from dopetracks chat, last month
Claude: [Searches chats, extracts Spotify links, creates playlist]
        Created "Dopetracks December" with 31 tracks
        → https://open.spotify.com/playlist/...
```

### Available Tools

| Tool | Description |
|------|-------------|
| `search_chats` | Search/list iMessage chats |
| `get_messages` | Get messages from a chat |
| `extract_spotify_links` | Extract Spotify URLs from a chat |
| `get_chat_stats` | Get Spotify sharing statistics |
| `spotify_auth_status` | Check Spotify authentication |
| `spotify_login` | Authenticate with Spotify |
| `create_playlist` | Create a playlist from track URLs |

## Development

```bash
# Run the server directly
python -m dopetracks_mcp.server

# Test imports
python -c "from dopetracks_mcp import server; print('OK')"
```

## Architecture

```
dopetracks_mcp/
├── server.py           # MCP server entry point
├── core/
│   ├── imessage.py     # iMessage database queries
│   └── spotify.py      # Spotify OAuth & API
└── tools/
    ├── chat_tools.py   # Chat-related MCP tools
    └── spotify_tools.py # Spotify-related MCP tools
```

The server reuses query functions from the main `dopetracks` package for iMessage database access.
