# Developer Guide

Complete guide for developers contributing to or modifying Dopetracks.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Running the Application](#running-the-application)
4. [Testing](#testing)
5. [Architecture Overview](#architecture-overview)
6. [Database Schema](#database-schema)
7. [API Documentation](#api-documentation)
8. [Contributing](#contributing)

---

## Development Setup

### Prerequisites

- **macOS** (required for Messages database access)
- **Python 3.11+**
- **Git**
- **Spotify Developer App** (for testing)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/namarks/dopeventures.git
cd dopeventures

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your Spotify credentials
```

### Environment Variables

Create a `.env` file in the project root:

```bash
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
DATABASE_URL=sqlite:///./.dopetracks/local.db
SECRET_KEY=your-secret-key-here
ENVIRONMENT=development
DEBUG=True
```

---

## Project Structure

```
dopeventures/
├── packages/
│   └── dopetracks/          # Main application package
│       ├── app.py           # FastAPI application (main entrypoint)
│       ├── config.py        # Configuration management
│       ├── database/        # Database models and connection
│       ├── processing/      # Data processing modules
│       ├── services/        # Business logic services
│       └── utils/           # Utility functions
├── DopetracksApp/           # Native macOS Swift app
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
├── dev_server.py            # Development server launcher
├── scripts/launch/          # Production launchers
└── requirements.txt         # Python dependencies
```

See **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for detailed architecture.

---

## Running the Application

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Run the application
python3 dev_server.py
```

The application will start on **http://127.0.0.1:8888**

### Using the Launcher (Optional)

For bundled/production runs (used by the Swift app):

```bash
python3 scripts/launch/app_launcher.py
```

See [LAUNCHER_GUIDE.md](./LAUNCHER_GUIDE.md) for more details.

### API Documentation

Once running, access:
- **Swagger UI**: http://127.0.0.1:8888/docs
- **ReDoc**: http://127.0.0.1:8888/redoc
- **Health Check**: http://127.0.0.1:8888/health

---

## Testing

### Current Status

**Note**: Automated tests are not yet implemented. The codebase is currently tested manually.

### Manual Testing

1. **Backend Testing**: Use Swagger UI at http://127.0.0.1:8888/docs
2. **Swift App Testing**: Run the app in Xcode and test UI interactions
3. **Integration Testing**: Test full workflow (chat search → playlist creation)

### Testing via Swagger UI

See **[TESTING_VIA_SWAGGER.md](./TESTING_VIA_SWAGGER.md)** for step-by-step guide.

### Manual Testing Checklist

See **[TESTING_GUIDE.md](./TESTING_GUIDE.md)** for complete testing workflow.

### Future: Adding Automated Tests

When adding tests, create a `tests/` directory with:
- `tests/unit/` - Unit tests for individual functions
- `tests/integration/` - Integration tests for API endpoints
- `tests/fixtures/` - Test data and fixtures

---

## Architecture Overview

### Backend

- **Framework**: FastAPI
- **Database**: SQLite (local)
- **ORM**: SQLAlchemy
- **OAuth**: Spotify OAuth 2.0 (single-user)

### Frontend

- **Technology**: SwiftUI native macOS app
- **Location**: `DopetracksApp/`
- **Communication**: HTTP REST API calls to backend (localhost:8888)

### Key Components

1. **Native macOS App**: SwiftUI interface, manages Python backend lifecycle
2. **FastAPI Backend**: REST API server, handles all business logic
3. **Spotify Integration**: OAuth flow, token management (single-user), playlist creation
4. **iMessage Processing**: Database queries, message extraction, FTS indexing, URL parsing
5. **Playlist Generation**: Track processing, batch adding, progress streaming

See **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for detailed architecture.

---

## Database Schema

### Core Tables

- **spotify_tokens**: Single-user Spotify OAuth tokens
- **local_cache**: Optional local data cache (currently unused)

**Note**: This is a single-user application. No user accounts or authentication tables.

See **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for complete schema.

---

## API Documentation

### Core Endpoints

- `GET /health` - Health check
- `GET /` - API information

### Chat Endpoints

- `GET /chats` - Get all chats
- `GET /chat-search-optimized` - Search chats
- `GET /chat/{chat_id}/recent-messages` - Get recent messages

### Playlist Endpoints

- `POST /create-playlist-optimized-stream` - Create playlist (streaming)
- `GET /user-playlists` - Get playlists
- `GET /user-profile` - Get Spotify profile

See **http://127.0.0.1:8888/docs** for interactive API documentation.

---

## Contributing

### Code Style

- Follow PEP 8 Python style guide
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and small

### Git Workflow

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Write/update tests
4. Commit with clear messages
5. Push and create a pull request

### Pull Request Guidelines

- Include description of changes
- Reference related issues
- Ensure tests pass
- Update documentation if needed

### Testing Requirements

- New features should include tests
- Bug fixes should include regression tests
- All tests must pass before merging

---

## Additional Resources

- **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** - Detailed architecture and design
- **[docs/TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Common issues and solutions
- **[docs/SPOTIFY_OAUTH_SETUP.md](./SPOTIFY_OAUTH_SETUP.md)** - Spotify OAuth configuration
- **[docs/REFACTOR_MIGRATION_GUIDE.md](./REFACTOR_MIGRATION_GUIDE.md)** - Migration guides

---

## Quick Reference

### Common Commands

```bash
# Start development server
python3 dev_server.py

# Note: Automated tests not yet implemented
# Manual testing via Swagger UI: http://127.0.0.1:8888/docs

# Check code style
flake8 packages/dopetracks

# Database migrations (if using Alembic)
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Useful Endpoints

- Health: http://127.0.0.1:8888/health
- API Docs: http://127.0.0.1:8888/docs
- Root: http://127.0.0.1:8888/

---

## Getting Help

- Check **[docs/TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** for common issues
- Review **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for architecture questions
- Open an issue on GitHub for bugs or feature requests

