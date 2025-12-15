# Testing Guide

This guide helps you test the Dopetracks application workflow to ensure everything works correctly.

## Quick Start Testing

### 1. Start the Application

```bash
# From project root
python start_multiuser.py
```

You should see:
```
🚀 Starting Dopetracks Multi-User Application...
📍 Health check: http://localhost:8888/health
🌐 API docs: http://localhost:8888/docs
🔐 Auth endpoints: http://localhost:8888/auth/
```

### 2. Verify Health Check

Open in browser or use curl:
```bash
curl http://localhost:8888/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "development",
  "version": "2.0.0"
}
```

### 3. Check API Documentation

Open in browser: **http://localhost:8888/docs**

This interactive Swagger UI lets you test all endpoints directly.

---

## Complete Workflow Testing

### Step 1: User Registration

**Endpoint:** `POST /auth/register`

**Using curl:**
```bash
curl -X POST http://localhost:8888/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPassword123!"
  }'
```

**Using API docs:**
1. Go to http://localhost:8888/docs
2. Find `POST /auth/register`
3. Click "Try it out"
4. Fill in the form
5. Click "Execute"

**Expected:** Returns user info and sets session cookie

### Step 2: Login

**Endpoint:** `POST /auth/login`

```bash
curl -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "username": "testuser",
    "password": "TestPassword123!"
  }'
```

**Expected:** Returns user info and session cookie

### Step 3: Get Spotify Client ID

**Endpoint:** `GET /get-client-id`

```bash
curl http://localhost:8888/get-client-id
```

**Expected:** Returns your Spotify client ID

### Step 4: Validate Messages Database

You have two options:

#### Option A: Validate System Username

**Endpoint:** `GET /validate-username?username=YOUR_MAC_USERNAME`

```bash
curl "http://localhost:8888/validate-username?username=$(whoami)" \
  -b cookies.txt
```

**Expected:** Confirms database path is accessible

#### Option B: Upload Database File

**Endpoint:** `POST /validate-chat-file`

```bash
curl -X POST http://localhost:8888/validate-chat-file \
  -b cookies.txt \
  -F "file=@/Users/YOUR_USERNAME/Library/Messages/chat.db"
```

**Expected:** Validates file and stores it

### Step 5: Get Chat List (NEW - Optimized)

**Endpoint:** `GET /chats`

```bash
curl http://localhost:8888/chats \
  -b cookies.txt
```

**Expected:** Returns list of all chats with statistics

### Step 6: Search Chats (NEW - Optimized)

**Endpoint:** `GET /chat-search-optimized?query=SEARCH_TERM`

```bash
curl "http://localhost:8888/chat-search-optimized?query=dope" \
  -b cookies.txt
```

**Expected:** Returns matching chats

### Step 7: Authorize Spotify

1. Get authorization URL:
   ```
   https://accounts.spotify.com/authorize?
     client_id=YOUR_CLIENT_ID&
     response_type=code&
     redirect_uri=http://localhost:8888/callback&
     scope=playlist-modify-public playlist-modify-private
   ```

2. Open in browser and authorize
3. You'll be redirected to `/callback` which stores tokens

**Verify tokens stored:**
```bash
curl http://localhost:8888/user-profile \
  -b cookies.txt
```

**Expected:** Returns your Spotify profile

### Step 8: Create Playlist (NEW - Optimized)

**Endpoint:** `POST /create-playlist-optimized`

```bash
curl -X POST http://localhost:8888/create-playlist-optimized \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "playlist_name": "Test Playlist",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "selected_chats": "[\"Dopetracks\", \"Music Group\"]"
  }'
```

**Expected:** Creates playlist and returns success message

### Step 9: Get Summary Stats (NEW)

**Endpoint:** `POST /summary-stats`

```bash
curl -X POST http://localhost:8888/summary-stats \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "chat_names": "[\"Dopetracks\"]",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'
```

**Expected:** Returns user statistics for selected chats

---

## Testing Checklist

### Basic Functionality
- [ ] Application starts without errors
- [ ] Health check returns "healthy"
- [ ] API docs accessible at `/docs`
- [ ] Database connection works

### Authentication
- [ ] User registration works
- [ ] User login works
- [ ] Session cookies are set
- [ ] Protected endpoints require authentication

### Database Access
- [ ] Can validate system username OR upload database file
- [ ] Database path is stored correctly
- [ ] Can access Messages database

### Chat Operations (Optimized)
- [ ] `/chats` returns chat list quickly
- [ ] `/chat-search-optimized` finds chats
- [ ] No upfront processing needed

### Spotify Integration
- [ ] Can get client ID
- [ ] OAuth flow works
- [ ] Tokens are stored
- [ ] Can access Spotify profile

### Playlist Creation (Optimized)
- [ ] `/create-playlist-optimized` works
- [ ] Only queries relevant messages (fast)
- [ ] Playlist created in Spotify
- [ ] Tracks added correctly

### Summary Stats
- [ ] `/summary-stats` generates statistics
- [ ] Stats are accurate
- [ ] Works for any date range/chat combination

---

## Testing with Python Script

Create a test script `test_workflow.py`:

```python
#!/usr/bin/env python3
"""Test the Dopetracks workflow."""
import requests
import json

BASE_URL = "http://localhost:8888"

def test_health():
    """Test health check."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✅ Health check passed")

def test_registration():
    """Test user registration."""
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPassword123!"
        }
    )
    assert response.status_code == 200
    print("✅ Registration passed")

def test_login(session):
    """Test login."""
    response = session.post(
        f"{BASE_URL}/auth/login",
        json={
            "username": "testuser",
            "password": "TestPassword123!"
        }
    )
    assert response.status_code == 200
    print("✅ Login passed")

def test_chats(session):
    """Test getting chat list."""
    response = session.get(f"{BASE_URL}/chats")
    assert response.status_code == 200
    chats = response.json()
    assert isinstance(chats, list)
    print(f"✅ Found {len(chats)} chats")

def main():
    """Run all tests."""
    print("🧪 Testing Dopetracks Workflow\n")
    
    # Test health
    test_health()
    
    # Test registration
    test_registration()
    
    # Test login with session
    session = requests.Session()
    test_login(session)
    
    # Test chats (requires database setup)
    try:
        test_chats(session)
    except Exception as e:
        print(f"⚠️  Chat test skipped: {e}")
        print("   (Requires Messages database setup)")
    
    print("\n✅ Basic workflow tests passed!")

if __name__ == "__main__":
    main()
```

Run it:
```bash
python scripts/debug/test_workflow.py
```

Note: A comprehensive test script is already available at `scripts/debug/test_workflow.py`.

---

## Common Issues & Solutions

### Issue: "Database not found"
**Solution:** Run `/validate-username` or `/validate-chat-file` first

### Issue: "Spotify not authorized"
**Solution:** Complete OAuth flow at `/callback`

### Issue: "No chat data available"
**Solution:** Use new optimized endpoints (`/chats`, `/chat-search-optimized`) - no upfront processing needed!

### Issue: Import errors
**Solution:** Make sure you're running from project root and virtual environment is activated

### Issue: Port already in use
**Solution:** 
```bash
pkill -f uvicorn
# Or change port in start_multiuser.py
```

---

## Performance Testing

### Test Optimized Endpoints Speed

```bash
# Time the optimized chat list endpoint
time curl http://localhost:8888/chats -b cookies.txt

# Should be < 1 second (vs 40-60 seconds for old approach)
```

### Compare Old vs New

**Old approach (deprecated):**
```bash
# This would take 40-60 seconds
curl http://localhost:8888/chat-search-progress -b cookies.txt
```

**New approach:**
```bash
# This should be < 1 second
curl http://localhost:8888/chats -b cookies.txt
```

---

## Frontend Testing

1. **Start backend:**
   ```bash
   python start_multiuser.py
   ```

2. **Start frontend (if separate):**
   ```bash
   cd website
   python3 -m http.server 8889
   ```

3. **Open browser:**
   - Frontend: http://localhost:8889
   - Backend API: http://localhost:8888
   - API Docs: http://localhost:8888/docs

4. **Test workflow in browser:**
   - Register/Login
   - Authorize Spotify
   - Validate database
   - Search chats
   - Create playlist

---

## Next Steps

Once basic tests pass:
1. Test with your actual Messages database
2. Test with multiple users
3. Test playlist creation with real data
4. Verify summary stats accuracy
5. Test edge cases (empty chats, no Spotify links, etc.)
