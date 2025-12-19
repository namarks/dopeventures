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
│       ├── api/             # API endpoints
│       │   ├── auth.py      # Authentication endpoints
│       │   └── admin.py    # Admin endpoints
│       ├── auth/            # Authentication utilities
│       ├── database/        # Database models and connection
│       ├── processing/      # Data processing modules
│       ├── services/        # Business logic services
│       └── utils/           # Utility functions
├── website/                 # Frontend (HTML/JS/CSS)
├── scripts/                 # Utility scripts
├── docs/                    # Documentation
├── start.py                 # Application entry point
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
python3 start.py
```

The application will start on **http://127.0.0.1:8888**

### Using the Launcher (Optional)

For development, you can use the launcher:

```bash
python3 launch.py
```

See [LAUNCHER_GUIDE.md](./LAUNCHER_GUIDE.md) for more details.

### API Documentation

Once running, access:
- **Swagger UI**: http://127.0.0.1:8888/docs
- **ReDoc**: http://127.0.0.1:8888/redoc
- **Health Check**: http://127.0.0.1:8888/health

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=packages/dopetracks

# Run specific test file
pytest tests/test_auth.py
```

### Testing via Swagger UI

See **[TESTING_VIA_SWAGGER.md](./TESTING_VIA_SWAGGER.md)** for step-by-step guide.

### Frontend Testing

See **[FRONTEND_TESTING_GUIDE.md](./FRONTEND_TESTING_GUIDE.md)** for complete frontend testing guide.

### Manual Testing Checklist

See **[TESTING_GUIDE.md](./TESTING_GUIDE.md)** for complete testing workflow.

---

## Architecture Overview

### Backend

- **Framework**: FastAPI
- **Database**: SQLite (dev) / PostgreSQL (production)
- **ORM**: SQLAlchemy
- **Authentication**: Session-based with bcrypt password hashing
- **OAuth**: Spotify OAuth 2.0

### Frontend

- **Technology**: Vanilla JavaScript, HTML, CSS
- **Served by**: FastAPI static file serving
- **Communication**: REST API calls to backend

### Key Components

1. **Authentication System**: User registration, login, session management
2. **Spotify Integration**: OAuth flow, token management, playlist creation
3. **iMessage Processing**: Database queries, message extraction, URL parsing
4. **Playlist Generation**: Track processing, batch adding, progress streaming

See **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for detailed architecture.

---

## Database Schema

### Core Tables

- **users**: User accounts
- **user_sessions**: Active user sessions
- **user_spotify_tokens**: Per-user Spotify OAuth tokens
- **user_data_cache**: Cached user data (messages, contacts)
- **user_uploaded_files**: User-uploaded database files
- **user_playlists**: Created playlists metadata
- **spotify_tokens**: Legacy global Spotify tokens (deprecated)

See **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for complete schema.

---

## API Documentation

### Authentication Endpoints

- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/me` - Get current user
- `GET /auth/status` - Check authentication status

### Playlist Endpoints

- `POST /create-playlist-optimized-stream` - Create playlist (streaming)
- `GET /user-playlists` - Get user's playlists
- `GET /user-profile` - Get Spotify profile

### Chat Endpoints

- `GET /chat-search-optimized` - Search chats
- `GET /chat/{chat_id}/recent-messages` - Get recent messages

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
python3 start.py

# Run tests
pytest

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
- Frontend: http://127.0.0.1:8888

---

## Getting Help

- Check **[docs/TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** for common issues
- Review **[PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)** for architecture questions
- Open an issue on GitHub for bugs or feature requests

