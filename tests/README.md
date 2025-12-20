# Tests

## Current Status

**Automated tests are not yet implemented.**

The codebase is currently tested manually:
- Backend API: Via Swagger UI at http://127.0.0.1:8888/docs
- Swift App: Manual testing in Xcode
- Integration: Full workflow testing (chat search → playlist creation)

## Future Test Structure

When adding automated tests, the structure should be:

```
tests/
├── unit/              # Unit tests for individual functions
│   ├── test_processing.py
│   ├── test_queries.py
│   └── test_utils.py
├── integration/       # Integration tests for API endpoints
│   ├── test_chat_endpoints.py
│   ├── test_playlist_endpoints.py
│   └── test_spotify_endpoints.py
└── fixtures/          # Test data and fixtures
    ├── sample_chat.db
    └── test_data.json
```

## Testing Requirements

- Use `pytest` as the test framework
- Mock external dependencies (Spotify API, file system)
- Test both success and error cases
- Include integration tests for critical workflows

