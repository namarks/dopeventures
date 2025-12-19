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

**Dopetracks** is a multi-user web application that extracts Spotify links from iMessage chat databases (macOS Messages app), processes and organizes shared music links, and automatically creates Spotify playlists from group chat conversations.

### Core Functionality
- **Multi-User Support**: Full user authentication and data isolation
- **iMessage Data Extraction**: Reads from macOS Messages database (`chat.db`)
- **Spotify Integration**: OAuth-based authentication and playlist creation
- **Data Processing**: Extracts messages, identifies Spotify links, and organizes by chat
- **Playlist Generation**: Creates Spotify playlists from selected chats and date ranges

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: Static HTML/JS/CSS served by FastAPI
- **Authentication**: Session-based with password hashing
- **OAuth**: Spotify OAuth 2.0 flow

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Frontend      │  (website/ - HTML/JS/CSS)
│   (Port 8889)   │
└────────┬────────┘
         │ HTTP Requests
         ▼
┌─────────────────┐
│   FastAPI App   │  (multiuser_app.py)
│   (Port 8888)   │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬─────────────┐
    ▼         ▼              ▼             ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│Database│ │Spotify   │ │File      │ │Processing│
│(SQLite │ │API       │ │Storage   │ │Pipeline  │
│/PG)    │ │          │ │          │ │          │
└────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Application Layers

1. **API Layer** (`multiuser_app.py`)
   - FastAPI application with route handlers
   - Authentication middleware
   - Request/response handling

2. **Service Layer** (`services/`)
   - `user_data.py`: Per-user data isolation and management
   - `session_storage.py`: In-memory session data caching

3. **Data Layer** (`database/`)
   - `models.py`: SQLAlchemy ORM models
   - `connection.py`: Database connection and initialization

4. **Processing Layer** (`processing/`)
   - `imessage_data_processing/`: Extract and clean Messages data
   - `spotify_interaction/`: Spotify API integration
   - `prepare_data_main.py`: Main data preparation pipeline

5. **Authentication Layer** (`auth/`, `api/auth.py`)
   - User registration, login, password reset
   - Session management
   - Role-based access control

---

## File Structure & Locations

### Project Root
```
dopeventures/
├── packages/dopetracks/               # Main application package (flattened structure)
├── website/                           # Frontend static files
├── user_uploads/                      # Per-user uploaded files
├── dopetracks_multiuser.db            # SQLite database (development)
├── .env                               # Environment variables (not in repo)
├── start_multiuser.py                 # Application entry point
└── requirements.txt                   # Python dependencies
```

### Backend Structure

#### Core Application
- **`packages/dopetracks/multiuser_app.py`**
  - Main FastAPI application
  - Route definitions and handlers
  - Static file serving (development)

- **`packages/dopetracks/config.py`**
  - Configuration management
  - Environment variable loading
  - Settings validation

#### Database
- **`packages/dopetracks/database/models.py`**
  - SQLAlchemy ORM models
  - User, Session, Spotify tokens, data cache, playlists

- **`packages/dopetracks/database/connection.py`**
  - Database connection management
  - Initialization and health checks

#### Authentication & Security
- **`packages/dopetracks/api/auth.py`**
  - Authentication endpoints (register, login, logout, password reset)

- **`packages/dopetracks/auth/security.py`**
  - Password hashing and validation
  - File content hashing
  - Secure filename generation

- **`packages/dopetracks/auth/dependencies.py`**
  - FastAPI dependencies for authentication
  - Current user retrieval

#### Services
- **`packages/dopetracks/services/user_data.py`**
  - Per-user data management
  - File upload handling
  - Data caching (session + database)
  - Spotify token storage

- **`packages/dopetracks/services/session_storage.py`**
  - In-memory session data storage
  - Temporary caching layer

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

#### Admin
- **`packages/dopetracks/api/admin.py`**
  - Admin-only endpoints
  - User management
  - System statistics

### Frontend Structure
- **`website/index.html`**: Main application page
- **`website/script.js`**: Frontend JavaScript logic
- **`website/config.js`**: Backend URL configuration

### Removed/Deprecated
- ❌ **`frontend_interface/`** - Removed (replaced by `multiuser_app.py`)
  - Old FastAPI implementation
  - No longer used
- ❌ **`tests/`** - Removed (outdated test files)
  - Will be replaced with proper test suite if needed

### Data Storage Locations

#### User Data
- **Uploaded Files**: `user_uploads/user_{id}/`
  - Per-user directory for uploaded chat.db files
  - Files stored with secure, hashed filenames

- **Database Cache**: `user_data_cache` table
  - Serialized DataFrames (pickle + base64)
  - Messages, contacts, handles data
  - Per-user isolation

- **Session Data**: 
  - In-memory: `session_storage` (temporary)
  - Database: `user_sessions` table (persistent)

#### Database Files
- **Main DB**: `dopetracks_multiuser.db` (root directory)
- **WAL Files**: `dopetracks_multiuser.db-wal`, `dopetracks_multiuser.db-shm`
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

- **`Procfile`**: Process definition for hosting platforms
- **`runtime.txt`**: Python version specification
- **`requirements.txt`**: Python package dependencies

### Migration Scripts
- **`scripts/utils/migrate_password_reset.py`**: Added password reset functionality
- **`scripts/utils/migrate_roles.py`**: Added user roles (user, admin, super_admin)
- **`scripts/utils/promote_admin.py`**: Utility to promote users to admin
- **`scripts/utils/reset_password.py`**: Utility script for password resets

---

## Database Schema

### Tables

#### `users`
User accounts and authentication.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `username` | String(50) | Unique username |
| `email` | String(100) | Unique email |
| `password_hash` | String(255) | Hashed password |
| `is_active` | Boolean | Account status |
| `role` | String(20) | user, admin, super_admin |
| `permissions` | Text | JSON permissions |
| `created_at` | DateTime | Account creation |
| `updated_at` | DateTime | Last update |

**Relationships:**
- One-to-many: `user_sessions`
- One-to-one: `user_spotify_tokens`
- One-to-many: `user_data_cache`
- One-to-many: `user_playlists`
- One-to-many: `user_password_resets`

#### `user_sessions`
Active user sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `session_id` | String(255) | Unique session identifier |
| `user_id` | Integer | Foreign key to users |
| `expires_at` | DateTime | Session expiration |
| `created_at` | DateTime | Session creation |
| `ip_address` | String(45) | Client IP (IPv6 support) |
| `user_agent` | String(500) | Client user agent |

**Indexes:**
- `idx_session_user_expires`: (user_id, expires_at)

#### `user_spotify_tokens`
Spotify OAuth tokens per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users (unique) |
| `access_token` | Text | OAuth access token |
| `refresh_token` | Text | OAuth refresh token |
| `token_type` | String(50) | Usually "Bearer" |
| `expires_at` | DateTime | Token expiration |
| `scope` | String(500) | OAuth scopes |
| `created_at` | DateTime | Token creation |
| `updated_at` | DateTime | Last update |

#### `user_data_cache`
Cached processed data per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users |
| `data_type` | String(50) | 'messages', 'contacts', 'handles', 'preferred_db_path' |
| `data_blob` | Text | JSON serialized data (or base64 pickle for DataFrames) |
| `file_hash` | String(64) | SHA256 hash of source file |
| `created_at` | DateTime | Cache creation |
| `updated_at` | DateTime | Last update |

**Indexes:**
- `idx_user_data_type`: (user_id, data_type)

#### `user_uploaded_files`
Track uploaded files per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users |
| `filename` | String(255) | Secure storage filename |
| `original_filename` | String(255) | Original filename |
| `file_size` | Integer | File size in bytes |
| `file_hash` | String(64) | SHA256 hash |
| `storage_path` | String(500) | File system path |
| `content_type` | String(100) | MIME type |
| `created_at` | DateTime | Upload time |

**Indexes:**
- `idx_user_files`: (user_id, created_at)

#### `user_playlists`
Track created playlists per user.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users |
| `spotify_playlist_id` | String(100) | Spotify playlist ID |
| `playlist_name` | String(255) | Playlist name |
| `tracks_count` | Integer | Number of tracks |
| `date_range_start` | String(10) | YYYY-MM-DD |
| `date_range_end` | String(10) | YYYY-MM-DD |
| `selected_chats` | Text | JSON array of chat names |
| `created_at` | DateTime | Creation time |

**Indexes:**
- `idx_user_playlists`: (user_id, created_at)

#### `user_password_resets`
Password reset tokens.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `user_id` | Integer | Foreign key to users |
| `reset_token` | String(255) | Unique reset token |
| `expires_at` | DateTime | Token expiration |
| `used_at` | DateTime | When token was used (nullable) |
| `created_at` | DateTime | Token creation |
| `ip_address` | String(45) | Request IP |
| `user_agent` | String(500) | Request user agent |

**Indexes:**
- `idx_reset_token_expires`: (reset_token, expires_at)
- `idx_user_resets`: (user_id, created_at)

---

## Key Components

### UserDataService
**Location**: `services/user_data.py`

Manages all user-specific data with complete isolation:
- **Data Caching**: Two-tier caching (session memory + database)
- **File Management**: Upload, storage, retrieval, deletion
- **Spotify Tokens**: OAuth token storage and retrieval
- **Database Paths**: Preferred Messages database path storage

### Authentication System
**Location**: `api/auth.py`, `auth/security.py`

- **Registration**: Username/email validation, password strength checking
- **Login**: Session-based authentication with secure cookies
- **Password Reset**: Token-based reset flow with expiration
- **Session Management**: Automatic expiration, cleanup

### Data Processing Pipeline
**Location**: `processing/prepare_data_main.py`

1. **Extraction**: Read from chat.db (system path or uploaded file)
2. **Cleaning**: Normalize message data, handle edge cases
3. **Enrichment**: Add metadata, identify Spotify links
4. **Caching**: Store processed DataFrames for quick access

### Spotify Integration
**Location**: `processing/spotify_interaction/`

- **OAuth Flow**: Per-user token management
- **URL Processing**: Extract and validate Spotify links
- **Metadata Caching**: Local SQLite cache for track metadata
- **Playlist Creation**: Generate playlists from selected chats

---

## Current State

### Working Features ✅

1. **User Management**
   - User registration with validation
   - Login/logout with session management
   - Password reset with secure tokens
   - Role-based access control (user, admin, super_admin)

2. **Data Processing**
   - iMessage database extraction (system path or file upload)
   - Message cleaning and normalization
   - Spotify link identification
   - Per-user data caching

3. **Spotify Integration**
   - OAuth 2.0 authentication (per-user)
   - Token storage and management
   - Playlist creation
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
DATABASE_URL=sqlite:///./dopetracks_multiuser.db

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

### User Registration & Setup

1. **Register Account**
   - POST `/auth/register` with username, email, password
   - Creates user record, initializes session
   - Returns user info and sets session cookie

2. **Authorize Spotify**
   - GET `/get-client-id` to get OAuth client ID
   - Redirect to Spotify authorization
   - Callback at `/callback` stores tokens

3. **Provide Messages Database**
   - Option A: Validate system username
     - GET `/validate-username?username=...`
     - Checks `/Users/{username}/Library/Messages/chat.db`
   - Option B: Upload database file
     - POST `/validate-chat-file` with .db file
     - Validates format and stores file

4. **Prepare Data**
   - GET `/chat-search-progress` (Server-Sent Events)
   - Extracts messages from database
   - Identifies Spotify links
   - Caches processed data

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
[Spotify Processing] → Extract URLs, fetch metadata
    ↓
[Cache Storage] → Store in user_data_cache table
    ↓
[Frontend Display] → Search, filter, create playlists
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
   python start_multiuser.py
   ```

4. **Access Application**
   - Frontend: http://localhost:8889 (if running separately)
   - Backend API: http://localhost:8888
   - API Docs: http://localhost:8888/docs

### Development Workflow

1. **Database Migrations**
   - Run migration scripts as needed
   - Database auto-initializes on first run
   - Check `database/connection.py` for schema creation

2. **Testing**
   - Use FastAPI's interactive docs: `/docs`
   - Test endpoints individually
   - Check logs in `backend.log`

3. **Frontend Development**
   - Edit files in `website/`
   - Update `config.js` for backend URL
   - FastAPI serves static files in development

### Common Tasks

#### Promote User to Admin
```bash
python scripts/utils/promote_admin.py <username>
```

#### Reset User Password
```bash
python scripts/utils/reset_password.py <username>
```

#### Check Database Health
```bash
curl http://localhost:8888/health
```

#### View Application Logs
```bash
tail -f backend.log
```

### Project Entry Points

- **Main Application**: `start_multiuser.py`
- **Direct FastAPI**: `packages/dopetracks/dopetracks/multiuser_app.py`
- **Legacy Interface**: `packages/dopetracks/dopetracks/frontend_interface/web_interface.py`

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
