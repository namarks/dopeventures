# Dopetracks Project Overview

> **Getting Started?** See [README.md](./README.md) for setup instructions, prerequisites, and usage guide.

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [File Structure & Locations](#file-structure--locations)
4. [Database Schema](#database-schema)
5. [Key Components](#key-components)
6. [Current State](#current-state)
7. [Configuration](#configuration)
8. [Workflows](#workflows)
9. [Development Guide](#development-guide)

---

## Project Overview

**Dopetracks** is a local macOS application that extracts Spotify links from iMessage chat databases (macOS Messages app), processes and organizes shared music links, and automatically creates Spotify playlists from group chat conversations. All data stays on your Mac - nothing is uploaded to external servers.

### Core Functionality
- **Local-First**: All data stays on your Mac
- **iMessage Data Extraction**: Reads from macOS Messages database (`chat.db`)
- **Spotify Integration**: OAuth-based authentication and playlist creation
- **Data Processing**: Extracts messages, identifies Spotify links, and organizes by chat
- **Playlist Generation**: Creates Spotify playlists from selected chats and date ranges

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite (local database)
- **Frontend**: Native macOS SwiftUI app
- **OAuth**: Spotify OAuth 2.0 flow (single-user)

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────┐
│      Native macOS App (SwiftUI)         │
│  ┌───────────────────────────────────┐  │
│  │  BackendManager                   │  │  ← Launches/manages Python backend
│  │  - Starts Python process          │  │
│  │  - Health checks                  │  │
│  └──────────────┬────────────────────┘  │
│                 │                       │
│  ┌──────────────▼────────────────────┐  │
│  │  APIClient                        │  │  ← HTTP client
│  │  - REST API calls                 │  │
│  └──────────────┬────────────────────┘  │
└─────────────────┼───────────────────────┘
                  │ HTTP REST API (localhost:8888)
                  ▼
┌─────────────────────────────────────────┐
│      FastAPI Backend (Python)           │
│      (app.py - Port 8888)               │
└──────────┬──────────────────────────────┘
           │
    ┌──────┴──────┬──────────────┬─────────────┐
    ▼             ▼              ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Database  │ │Spotify   │ │Messages  │ │Processing│
│(SQLite)  │ │API       │ │chat.db   │ │Pipeline  │
│          │ │(External)│ │(File)    │ │          │
│-Tokens   │ │          │ │          │ │-FTS      │
│-Cache    │ │          │ │          │ │-Search   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘
```

**Key Points:**
- **Swift App** manages and communicates with the Python backend
- **BackendManager** launches the Python process automatically
- **APIClient** handles all HTTP communication
- **Backend** accesses local files (chat.db) and external APIs (Spotify)
- **Single-user**: No authentication, all data is local

### Application Layers

1. **API Layer** (`app.py`)
   - FastAPI application with REST API endpoints
   - Request/response handling
   - Single-user setup (no authentication needed)

2. **Service Layer** (`services/`)
   - `session_storage.py`: In-memory session data caching

3. **Data Layer** (`database/`)
   - `models.py`: SQLAlchemy ORM models
   - `connection.py`: Database connection and initialization

4. **Processing Layer** (`processing/`)
   - `imessage_data_processing/`: Extract and clean Messages data
   - `spotify_interaction/`: Spotify API integration
   - `prepare_data_main.py`: Main data preparation pipeline

5. **Utilities** (`utils/`)
   - Helper functions for database paths
   - Configuration management

---

## File Structure & Locations

### Project Root
```
dopeventures/
├── packages/dopetracks/               # Main application package 
├── DopetracksApp/                     # Native macOS Swift app
├── user_uploads/                      # Uploaded chat.db files (optional)
├── .env                               # Environment variables (not in repo)
├── dev_server.py                      # Development server launcher
├── scripts/launch/app_launcher.py    # Production/bundled app launcher
└── requirements.txt                   # Python dependencies
```

### Backend Structure

#### Core Application
- **`packages/dopetracks/app.py`**
  - Main FastAPI application
  - Route definitions and handlers

- **`packages/dopetracks/config.py`**
  - Configuration management
  - Environment variable loading
  - Settings validation

#### Database
- **`packages/dopetracks/database/models.py`**
  - SQLAlchemy ORM models
  - `SpotifyToken`: Single-user Spotify OAuth tokens
  - `LocalCache`: Local data cache (optional, currently unused)

- **`packages/dopetracks/database/connection.py`**
  - Database connection management
  - Initialization and health checks

#### Services
- **`packages/dopetracks/services/session_storage.py`**
  - In-memory session data storage (temporary caching)

#### Data Processing
- **`packages/dopetracks/processing/prepare_data_main.py`**
  - Main data preparation entry point (used by deprecated endpoint)
  - Orchestrates extraction and cleaning

- **`packages/dopetracks/processing/imessage_data_processing/`**
  - `optimized_queries.py`: **NEW** - Direct SQL queries for on-demand processing
  - `data_pull.py`: Extract messages from chat.db
  - `data_cleaning.py`: Clean and normalize data
  - `data_enrichment.py`: Enrich with additional metadata
  - `generate_summary_stats.py`: Generate statistics

- **`packages/dopetracks/processing/spotify_interaction/`**
  - `spotify_db_manager.py`: Spotify URL processing and caching
  - `create_spotify_playlist.py`: Playlist creation logic

- **`packages/dopetracks/processing/contacts_data_processing/`**
  - `import_contact_info.py`: Contact information processing

#### API Endpoints
- **`packages/dopetracks/app.py`**
  - All REST API endpoints defined in `app.py`
  - Chat search and message endpoints
  - FTS indexing endpoints
  - Spotify OAuth endpoints
  - Playlist creation endpoints

### Native macOS App
- **`DopetracksApp/`**: SwiftUI native macOS application
- **`DopetracksApp/DopetracksApp/`**: Main Swift app code
  - **`Models/`**: Data models (Chat, Message, Playlist, SpotifyProfile)
  - **`Services/`**: API client and backend manager
  - **`Views/`**: SwiftUI views (ChatListView, PlaylistCreationView, etc.)

### Data Storage Locations

#### Application Data
- **Uploaded Files** (optional): `user_uploads/`
  - Optional directory for uploaded chat.db files
  - Used if user wants to process a different Messages database

- **Session Data**: 
  - In-memory: `session_storage` (temporary caching)

#### Database Files
- **Main DB**: `~/.dopetracks/local.db` (user data directory)
- **WAL Files**: `local.db-wal`, `local.db-shm` (if using WAL mode)
  - SQLite transaction files (auto-generated)

#### Spotify Cache
- **Location**: `~/.spotify_cache/spotify_cache.db`
  - Metadata cache for Spotify URLs
  - Reduces API calls
  - Not in repository (user-specific)

### Configuration Files
- **`.env`**: Environment variables (not in repo)
  - Spotify credentials
  - Database URL
  - Security keys
  - See `.env.example` for template
- **`requirements.txt`**: Python dependencies

---

## Database Schema

### Tables

#### `spotify_tokens`
Single-user Spotify OAuth tokens.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `access_token` | Text | OAuth access token |
| `refresh_token` | Text | OAuth refresh token |
| `token_type` | String(50) | Usually "Bearer" |
| `expires_at` | DateTime | Token expiration |
| `scope` | String(500) | OAuth scopes |
| `created_at` | DateTime | Token creation |
| `updated_at` | DateTime | Last update |

**Note**: This is a single-user application. Only one set of Spotify tokens is stored.

#### `local_cache` (optional, currently unused)
Local cache for processed data.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `cache_key` | String(100) | Unique cache key |
| `data_blob` | Text | JSON serialized data |
| `created_at` | DateTime | Cache creation |
| `updated_at` | DateTime | Last update |

---

## Key Components

### Session Storage
**Location**: `services/session_storage.py`

- **In-Memory Caching**: Temporary session data storage
- **Data Types**: Messages, contacts, handles data
- **Lifecycle**: Cleared when session ends

### Data Processing Pipeline
**Location**: `processing/prepare_data_main.py`

1. **Extraction**: Read from chat.db (defaults to `~/Library/Messages/chat.db`)
2. **Cleaning**: Normalize message data, handle edge cases
3. **Enrichment**: Add metadata, identify Spotify links
4. **FTS Indexing**: Full-text search index for fast message searches

### Spotify Integration
**Location**: `processing/spotify_interaction/`

- **OAuth Flow**: Single-user token management (stored in `spotify_tokens` table)
- **URL Processing**: Extract and validate Spotify links
- **Metadata Caching**: Local SQLite cache for track metadata (`~/.spotify_cache/spotify_cache.db`)
- **Playlist Creation**: Generate playlists from selected chats

---

## Current State

### Working Features ✅

1. **Data Processing**
   - iMessage database extraction (defaults to `~/Library/Messages/chat.db`)
   - Message cleaning and normalization
   - Spotify link identification
   - Full-text search (FTS) indexing for fast searches
   - In-memory session caching

2. **Spotify Integration**
   - OAuth 2.0 authentication (single-user)
   - Token storage and management (in `spotify_tokens` table)
   - Playlist creation from selected chats and date ranges

3. **Native macOS App**
   - SwiftUI interface
   - Automatic backend management
   - Chat browsing and search
   - Playlist creation workflow
   - Metadata caching

4. **File Management**
   - Secure file uploads
   - Per-user file isolation
   - File validation (Messages database format)
   - Storage path management

5. **Chat Search**
   - Search chats by name
   - Display chat statistics (members, messages, Spotify links)
   - Filter by date ranges

### Known Issues & Limitations ⚠️

1. **User Message Counting**
   - Currently uses `is_from_me` column or username matching
   - TODO: Map `handle_id` to username for better accuracy
   - Issue: Numeric handle IDs don't directly map to usernames

2. **Cloud Storage**
   - Local file storage implemented
   - TODO: S3/GCS integration for production
   - Currently stores files in `user_uploads/` directory

3. **Chat Search Optimization**
   - Basic search implemented
   - TODO: Optimize for large datasets
   - Could benefit from full-text search indexing

4. **Session Storage**
   - In-memory session storage (temporary)
   - Database persistence for long-term
   - TODO: Redis integration for production scaling

### Pending TODOs 📋

1. **Map handle_id to username** for accurate user message counting
2. **Cloud storage support** (S3/GCS) for file uploads
3. **Optimized chat search** implementation
4. **Redis integration** for session storage in production
5. **Email service** for password reset (currently logs to console)

---

## Configuration

### Environment Variables

#### Required
```bash
# Spotify API (required)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Security (required in production)
SECRET_KEY=your-secret-key-minimum-32-chars
```

#### Database
```bash
# Development (SQLite - default)
DATABASE_URL=sqlite:///./local.db

# Production (PostgreSQL - recommended)
DATABASE_URL=postgresql://user:pass@host:port/dbname
```

#### Optional
```bash
# Environment
ENVIRONMENT=development  # or 'production'
DEBUG=True
LOG_LEVEL=INFO

# Sessions
ACCESS_TOKEN_EXPIRE_MINUTES=60
SESSION_EXPIRE_HOURS=24

# File Storage
STORAGE_TYPE=local  # or 's3', 'gcs'
MAX_FILE_SIZE_MB=100

# CORS (comma-separated or JSON array)
CORS_ORIGINS=["http://localhost:8889", "http://localhost:3000"]
```

### Configuration Loading
**Location**: `config.py`

- Loads from `.env` file (development)
- Validates required settings on import
- Provides defaults for optional settings
- Environment-aware (development vs production)

---

## Workflows

### Setup & Spotify Authorization

1. **Authorize Spotify**
   - GET `/get-client-id` to get OAuth client ID
   - Redirect to Spotify authorization
   - Callback at `/callback` stores tokens

2. **Access Messages Database**
   - App automatically reads from `~/Library/Messages/chat.db`
   - Requires Full Disk Access permission on macOS
   - FTS indexing can be triggered via `/fts/index` endpoint

### Chat Search & Playlist Creation

1. **Search Chats**
   - GET `/chat-search?query=...`
   - Returns matching chats with statistics
   - Shows members, message counts, Spotify links

2. **Create Playlist**
   - Select chats and date range
   - POST to playlist creation endpoint
   - Uses Spotify API to create playlist
   - Adds tracks from selected chats

### Data Processing Flow

```
chat.db (input)
    ↓
[Data Pull] → Extract messages, handles, chats
    ↓
[Data Cleaning] → Normalize, deduplicate, validate
    ↓
[Data Enrichment] → Add metadata, identify Spotify links
    ↓
[FTS Indexing] → Create full-text search index (optional, for faster searches)
    ↓
[Spotify Processing] → Extract URLs, fetch metadata
    ↓
[Swift App Display] → Search, filter, create playlists
```

---

## Development Guide

### Quick Start

1. **Setup Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Spotify credentials
   ```

3. **Start Application**
   ```bash
   python3 dev_server.py
   ```

4. **Access Application**
   - Backend API: http://127.0.0.1:8888
   - API Docs: http://127.0.0.1:8888/docs
   - Swift App: Open in Xcode and run

### Development Workflow

1. **Database Setup**
   - Database auto-initializes on first run
   - Check `database/connection.py` for schema creation

2. **Testing**
   - Use FastAPI's interactive docs: `/docs`
   - Test endpoints individually
   - Check logs in `backend.log`

3. **Swift App Development**
   - Open `DopetracksApp/DopetracksApp.xcodeproj` in Xcode
   - Edit Swift files in `DopetracksApp/DopetracksApp/`
   - Backend runs automatically via `BackendManager`

### Common Tasks

#### Check Database Health
```bash
curl http://localhost:8888/health
```

#### View Application Logs
```bash
tail -f backend.log
```

### Project Entry Points

- **Development Server**: `dev_server.py` (simple launcher with auto-reload)
- **Production Launcher**: `scripts/launch/app_launcher.py` (used by Swift app)
- **Direct FastAPI**: `packages/dopetracks/app.py` (can be run directly with uvicorn)

---

## Additional Resources

- **Deployment Guide**: See `docs/DEPLOYMENT.md`
- **Main README**: See `README.md` for setup instructions
- **API Documentation**: Available at `/docs` when running
- **Environment Template**: See `.env.example`

### Documentation Files

Additional documentation is in the `docs/` folder:
- **EFFICIENCY_ANALYSIS.md** - Refactor analysis and optimization details
- **REFACTOR_MIGRATION_GUIDE.md** - Migration guide for new endpoints
- **CLEANUP_SUMMARY.md** - Files removed during cleanup
- **STRUCTURE_REORGANIZATION.md** - Package structure changes

---

## Version Information

- **Application Version**: 2.0.0
- **Python Version**: 3.11+
- **FastAPI**: Latest stable
- **Database**: SQLite (dev) / PostgreSQL (prod)

---

*Last Updated: Based on current codebase state*
*For questions or issues, refer to the codebase or create an issue in the repository.*
