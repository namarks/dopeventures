# Dopetracks Code Review

Comprehensive review of the Dopetracks codebase — a local-first macOS app that creates Spotify playlists from songs shared in iMessage group chats.

**Stack:** Python FastAPI backend + Swift/SwiftUI macOS frontend
**Date:** 2026-02-08

---

## Table of Contents

1. [Critical Issues](#1-critical-issues)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [Backend Issues (Python)](#3-backend-issues-python)
4. [Frontend Issues (Swift)](#4-frontend-issues-swift)
5. [Performance Concerns](#5-performance-concerns)
6. [Test Coverage & DevOps](#6-test-coverage--devops)
7. [Code Duplication](#7-code-duplication)
8. [Dependency Concerns](#8-dependency-concerns)
9. [Summary & Recommendations](#9-summary--recommendations)

---

## 1. Critical Issues

### 1.1 FTS Query Injection

**File:** `packages/dopetracks/processing/imessage_data_processing/fts_indexer.py:292-308`

User-controlled search terms are interpolated into FTS5 MATCH queries. The escaping only handles double-quotes, but FTS5 has its own operators (`AND`, `OR`, `NOT`, `NEAR`, `*`) that can be injected to manipulate query logic.

```python
escaped_term = search_term.replace('"', '""')
fts_query = f'extracted_text MATCH "{escaped_term}" OR original_text MATCH "{escaped_term}"'
# ...later interpolated into SQL with f-string
```

**Fix:** Use parameterized queries with `?` placeholders for the MATCH value.

### 1.2 Missing Functions — Silent Feature Failure

**File:** `packages/dopetracks/processing/imessage_data_processing/optimized_queries.py:826-827`

`get_contacts_db_path` and `clean_phone_number` are imported from `import_contact_info` but do not exist anywhere in the codebase. Every call site wraps them in `try/except`, so the contact-based chat search silently fails on every invocation. This means the contacts database search path in `search_chats_by_name()` and `advanced_chat_search()` is dead code.

### 1.3 ~5% Test Coverage

The project has exactly **3 tests** across ~20 source modules. Zero tests for:
- All FastAPI endpoints
- Spotify OAuth flow and token refresh
- FTS indexing
- Contact resolution
- All Swift frontend code

See [Section 6](#6-test-coverage--devops) for full details.

### 1.4 Backend Killed on Window Focus Loss (macOS)

**File:** `DopetracksApp/App/DopetracksApp.swift:34-38`

```swift
.onChange(of: scenePhase) { newPhase in
    if newPhase == .inactive || newPhase == .background {
        backendManager.stopBackend()
    }
}
```

On macOS, `.inactive` triggers when the window loses focus (e.g., user switches to another app). The backend is terminated every time the user clicks away, then must be restarted when they return. Only `.background` (or app termination) should trigger `stopBackend`.

### 1.5 `URLSession` Leak in Health Check Loop

**File:** `DopetracksApp/App/Services/BackendManager.swift:326-330`

A new `URLSession` is created on every call to `checkBackendHealth()`. This runs every 5 seconds indefinitely, plus up to 30 times during startup. Each `URLSession` holds connection pools and caches that are never invalidated.

**Fix:** Create the session once and store it as a property, or use `URLSession.shared`.

---

## 2. Security Vulnerabilities

### 2.1 SQL Injection via `order_by` Parameter

**File:** `packages/dopetracks/processing/imessage_data_processing/query_builders.py:77`

```python
ORDER BY {order_by}
```

The `order_by` parameter is interpolated directly into SQL via f-string. Current callers pass hardcoded values, but there is no validation at this boundary.

### 2.2 Default Secret Key in Production

**File:** `packages/dopetracks/config.py:40-41`

```python
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
```

While there is a validation check for production mode, the default key is committed to the repository. The validation only logs a warning (via `validate_required_settings`) and does not prevent startup.

### 2.3 XSS in OAuth Error Page

**File:** `packages/dopetracks/app.py:548-560`

```python
html_content = f"""
    ...
    <p>Error: {error}</p>
    ...
"""
```

The `error` query parameter from Spotify's OAuth callback is interpolated directly into HTML without escaping. An attacker could craft a URL with malicious JavaScript in the `error` parameter.

### 2.4 `HTMLResponse` Not Imported

**File:** `packages/dopetracks/app.py:561`

`HTMLResponse` is used in the callback endpoint but is not imported at the top of the file. This will raise a `NameError` at runtime when the error path is hit.

### 2.5 `resolve_short_url()` Has No Timeout or Error Handling

**File:** `packages/dopetracks/utils/utility_functions.py:44-46`

```python
def resolve_short_url(short_url):
    response = requests.head(short_url, allow_redirects=True)
    return response.url
```

No timeout, no exception handling, no status code check. A malformed URL or unresponsive server will hang indefinitely.

---

## 3. Backend Issues (Python)

### 3.1 `app.py` is 1,999 Lines

The main application file contains all route handlers, helper functions, HTML templates, and business logic in a single file. Endpoint handlers contain significant inline logic (e.g., the playlist creation endpoint at lines 1180-1528 is 350 lines). Consider splitting into:
- `routes/spotify.py` — OAuth, profile, playlists
- `routes/chats.py` — Chat search, messages
- `routes/contacts.py` — Contact photo, debug
- `routes/fts.py` — FTS indexing and status

### 3.2 Connection Leak in FTS Indexer

**File:** `packages/dopetracks/processing/imessage_data_processing/fts_indexer.py:134-135`

SQLite connections are opened without `with` blocks or `try/finally`. If an exception occurs between open and close, the connection leaks.

### 3.3 `PRAGMA synchronous = OFF`

**File:** `packages/dopetracks/processing/imessage_data_processing/prepared_messages.py:501,580`

Disabling synchronous writes means data can be lost on power failure or crash. The pragma applies to the entire connection and is never restored.

### 3.4 Bare `except: pass` Throughout

Multiple modules silently swallow all exceptions:
- `processing/contacts_data_processing/import_contact_info.py:75-76,97-104`
- `processing/imessage_data_processing/optimized_queries.py:507,549,565,585`
- `processing/imessage_data_processing/prepared_messages.py:131-133,151,164-165`

These make debugging impossible when things silently fail.

### 3.5 `print()` Used Instead of `logging`

**File:** `processing/imessage_data_processing/data_enrichment.py:110`
**File:** `processing/spotify_interaction/spotify_db_manager.py:118,133,277`

Debug `print()` statements in production code are invisible when stdout is not monitored.

### 3.6 Thread-Unsafe Global Contact Cache

**File:** `processing/contacts_data_processing/import_contact_info.py:10-11`

The module-level `_CONTACT_CACHE` dict and `_LOAD_ATTEMPTED` flag are accessed without synchronization. In a multi-threaded web server context, concurrent requests can corrupt the cache.

### 3.7 Module-Level Environment Variable Reads

**File:** `processing/spotify_interaction/create_spotify_playlist.py:12-14`

```python
CLIENT_ID=os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET=os.getenv('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI=os.getenv('SPOTIFY_REDIRECT_URI')
```

Evaluated at import time, before `.env` loading. Load order dependent — values may be `None`.

### 3.8 `create_spotify_playlist.py` `__main__` Block Broken

**File:** `processing/spotify_interaction/create_spotify_playlist.py:253`

`main()` requires two positional arguments but is called with none. Will always raise `TypeError`.

### 3.9 Duplicate Spotify API Calls

**File:** `processing/spotify_interaction/create_spotify_playlist.py:233-246`

`main()` fetches all playlist items and deduplicates, then passes to `add_tracks_to_playlist()` which fetches all items and deduplicates again. This doubles the API calls.

---

## 4. Frontend Issues (Swift)

### 4.1 `BackendManager` Not `@MainActor`

**File:** `DopetracksApp/App/Services/BackendManager.swift`

`@Published` properties are mutated from various threads without main-actor isolation. `stopBackend()` and `startHealthCheck()` can run off the main thread. Publishing changes from a background thread to `@Published` on an `ObservableObject` is undefined behavior in SwiftUI.

**Fix:** Annotate `BackendManager` with `@MainActor`.

### 4.2 `@StateObject` Wrapping Externally-Created Object

**File:** `DopetracksApp/App/ContentView.swift:13,17-19`

```swift
@StateObject private var chatListViewModel: ChatListViewModel

init(chatListViewModel: ChatListViewModel) {
    _chatListViewModel = StateObject(wrappedValue: chatListViewModel)
}
```

`@StateObject` is designed to own and create the object. Wrapping an externally-created object should use `@ObservedObject`.

### 4.3 Force-Unwrapped URLs Throughout APIClient

**File:** `DopetracksApp/App/Services/APIClient.swift:26,38,47,262,357,371,385`

Every `URL(string:)!` will crash if the string is malformed. Same issue in views:
- `DopetracksApp/App/Views/ChatDetailView.swift:211`
- `DopetracksApp/App/Views/SettingsView.swift:115`

### 4.4 `DateFormatter` Created Per Decode Call

**Files:** `DopetracksApp/App/Models/Chat.swift:43-46`, `Message.swift:73-76,121-124`

`DateFormatter` is expensive to create. A new instance is allocated for every `Chat` or `Message` decoded. When decoding hundreds of messages, this creates hundreds of formatters.

**Fix:** Use `static let` constant formatters.

### 4.5 `Message.id` Collision Risk

**File:** `DopetracksApp/App/Models/Message.swift:68`

```swift
self.id = "\(textValue.prefix(20))_\(dateString)"
```

If two messages share the same first 20 characters and timestamp, they get the same `id`, causing SwiftUI `ForEach` to misbehave.

### 4.6 View-Layer Business Logic

- `DopetracksApp/App/Views/SettingsView.swift:139-227` — `.env` parsing, saving, and backend restart
- `DopetracksApp/App/Views/PlaylistCreationView.swift:113-136` — API call from view

These violate MVVM. Business logic should be in ViewModels.

### 4.7 Race Condition in `onAppear` Auto-Selection

**File:** `DopetracksApp/App/ViewModels/ChatListViewModel.swift:30-46`

Three independent `Task` blocks are launched. The third reads `chats.first` before `loadAllChats()` may have completed, so `chats` could be empty.

### 4.8 `#file` Path Resolution Fragile in Release Builds

**File:** `DopetracksApp/App/Services/BackendManager.swift:106-111`

`#file` resolves at compile time. In distributed builds, the source path won't exist. Should use `Bundle.main.resourceURL`.

### 4.9 Redundant `MainActor.run` in `@MainActor` Classes

**Files:** `ChatDetailViewModel.swift:31-37,43-49,64-70,72-78,82-86`, `ChatListViewModel.swift:105-108,128-133`

These classes are `@MainActor`, so `await MainActor.run {}` is redundant within them.

---

## 5. Performance Concerns

### 5.1 N+1 Query Pattern in `get_chat_list()`

**File:** `packages/dopetracks/processing/imessage_data_processing/optimized_queries.py:489-599`

For each chat, the code opens new connections to query participants, fetch recent messages, and resolve contact names. For 200 chats, this means 200+ separate database connections and potentially thousands of contact lookups.

### 5.2 Loading All Messages Into Memory for FTS

**File:** `packages/dopetracks/processing/imessage_data_processing/fts_indexer.py:157`

```python
df = pd.read_sql_query(query, source_conn)
```

Loads the entire result set into a pandas DataFrame, then filters in Python. For large message databases, this can exhaust memory. Deduplication should happen in SQL.

### 5.3 `get_indexed_message_ids()` Loads All IDs Into a Set

**File:** `packages/dopetracks/processing/imessage_data_processing/fts_indexer.py:96-103`

Every indexed message ID is loaded into a Python set. Should use SQL-level deduplication.

### 5.4 Per-URL Cache Lookup

**File:** `packages/dopetracks/processing/spotify_interaction/spotify_db_manager.py:275-284`

Each URL triggers a separate DB connection and query. For hundreds of URLs, a single bulk query would be far more efficient.

### 5.5 `apply(axis=1)` on Full DataFrame

**File:** `packages/dopetracks/processing/imessage_data_processing/data_enrichment.py:126-130`

`apply(axis=1)` is one of the slowest pandas operations. Should use vectorized `np.where` or `pd.Series.where`.

---

## 6. Test Coverage & DevOps

### 6.1 Test Coverage

| Area | Tests | Status |
|------|-------|--------|
| FastAPI endpoints (19+) | 0 | Not tested |
| Spotify OAuth/token refresh | 0 | Not tested |
| iMessage data processing (7 modules) | 3 | Minimal |
| FTS indexer | 0 | Not tested |
| Contact resolution | 0 | Not tested |
| Configuration/security | 0 | Not tested |
| Swift frontend (20 files) | 0 | Not tested |
| **Total** | **3** | **~5%** |

No `conftest.py`, no shared fixtures, no pytest configuration in `pyproject.toml`.

### 6.2 Deployment Configuration

- **Procfile** missing `PYTHONPATH` setup — `from dopetracks.app import app` will fail on Heroku
- Single uvicorn worker, no gunicorn — cannot utilize multiple cores
- No `release` process for database migrations (Alembic is in requirements)
- No `gunicorn` in `requirements.txt`

### 6.3 `dev_server.py` Contradictions

Line 5 docstring says "Starts uvicorn with auto-reload" but line 106 has `reload=False`.

### 6.4 Debug Scripts — Wrong `.env` Path

All 5 Spotify debug scripts look for `.env` at `Path(__file__).parent / ".env"` (resolves to `scripts/debug/.env`). The actual `.env` is at the project root.

### 6.5 Broken Import Paths in Utility Scripts

`scripts/utils/promote_admin.py` and `scripts/utils/reset_password.py` add incorrect paths to `sys.path` and will crash with `ModuleNotFoundError`.

### 6.6 Hardcoded Developer Paths

- `scripts/debug/check_chat_service.py:15` — `/Users/nmarks/Library/Messages/chat.db`
- `scripts/utils/setup_and_run.sh:8` — `/Users/nmarks/root_code_repo/venvs/dopetracks_env`

### 6.7 `setup.sh` Gaps

- No Python version validation despite requiring 3.11+
- No `chmod 600 .env` to restrict file permissions
- No lockfile mechanism

### 6.8 `pyproject.toml` Issues

- Zero runtime dependencies declared (all are in `requirements.txt` only)
- No `[tool.pytest.ini_options]` section
- No linting/formatting/type-checking configuration
- Uses Poetry but no `poetry.lock` exists

---

## 7. Code Duplication

### 7.1 Major Duplications

| Duplicated Code | Locations | Lines |
|----------------|-----------|-------|
| `advanced_chat_search` + streaming variant | `optimized_queries.py:960-1350` | ~400 lines |
| `query_messages_with_urls` + `query_spotify_messages` | `optimized_queries.py:635-752` | ~120 lines |
| Ingestion logic | `prepared_messages.py:612-721` + `ingestion.py:27-185` | ~260 lines |
| Contact search logic | `optimized_queries.py:825-885` + `optimized_queries.py:992-1061` | ~120 lines |
| `detect_reaction()` | `data_enrichment.py:6-11` + `parsing_utils.py:35-42` | Identical |
| `domain_matches()` | `parsing_utils.py:95` + `parsing_utils.py:157` | Identical |
| Handle normalization | `handle_utils.py`, `prepared_messages.py`, `optimized_queries.py` | 3 variants |
| DB path resolution | `helpers.py`, `utility_functions.py`, `imessage_db.py` | 3 functions |

---

## 8. Dependency Concerns

### 8.1 Unmaintained/Vulnerable

| Package | Last Release | Concern |
|---------|-------------|---------|
| `python-jose` | 2021 | Known JWT vulnerabilities. Replace with `PyJWT`. |
| `passlib` | 2020 | No security patches. Use `bcrypt` directly. |

### 8.2 Unnecessary Dependencies

| Package | Reason |
|---------|--------|
| `flask`, `flask-session` | Project uses FastAPI, not Flask |
| `dj-database-url` | Django utility, project uses SQLAlchemy |
| `boto3` | Listed as "optional" but always installed (~80MB) |
| `requests` + `httpx` | Redundant — `httpx` can replace `requests` |

### 8.3 No Lockfile

All dependencies use `>=` with no upper bound. No `requirements.lock`, `poetry.lock`, or `pip-compile` output. Builds are not reproducible.

---

## 9. Summary & Recommendations

### Priority 1 — Fix Immediately

1. **FTS query injection** — Use parameterized queries for MATCH values
2. **XSS in OAuth error page** — HTML-escape the `error` parameter
3. **Import `HTMLResponse`** — Add the missing import
4. **Backend killed on `.inactive`** — Change to only trigger on app termination
5. **`URLSession` leak** — Create once and reuse
6. **`BackendManager` thread safety** — Add `@MainActor` annotation

### Priority 2 — Fix Soon

7. **Add missing functions** (`get_contacts_db_path`, `clean_phone_number`) or remove dead code
8. **Connection leaks** in `fts_indexer.py` — use context managers
9. **Replace `python-jose`** with `PyJWT`
10. **Fix `@StateObject` misuse** in `ContentView` — use `@ObservedObject`
11. **Add `PYTHONPATH`** to Procfile for deployment
12. **Fix debug scripts** `.env` path resolution

### Priority 3 — Address in Refactoring

13. **Split `app.py`** into route modules
14. **Eliminate code duplication** (~900+ lines of duplicated logic)
15. **Add test infrastructure** — conftest.py, fixtures, API endpoint tests
16. **Add a dependency lockfile**
17. **Remove unused dependencies** (Flask, dj-database-url)
18. **N+1 query optimization** in `get_chat_list()`
19. **Memory optimization** in FTS indexer
20. **Move view business logic to ViewModels** (SettingsView, PlaylistCreationView)
