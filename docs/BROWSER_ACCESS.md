# Browser Access Guide

## What URLs to Use

When the server is running, you can access:

### 1. API Documentation (Interactive - Best for Testing)
```
http://localhost:8888/docs
```
This is the **Swagger UI** - you can test all endpoints directly here!

### 2. Health Check
```
http://localhost:8888/health
```
Should return JSON with status information.

### 3. Root Endpoint
```
http://localhost:8888/
```
Returns welcome message.

### 4. Frontend (if website directory is found)
```
http://localhost:8888/
```
Serves the frontend HTML if website directory is properly configured.

## How to Know Server is Ready

Look for this in your terminal:
```
INFO:     Uvicorn running on http://0.0.0.0:8888 (Press CTRL+C to quit)
INFO:     Started reloader process [XXXXX]
INFO:     Started server process [XXXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**Wait for "Application startup complete"** before trying to access URLs.

## Quick Test

1. **Start server:**
   ```bash
   source /Users/nmarks/root_code_repo/venvs/dopetracks_env/bin/activate
   python3 start.py
   ```

2. **Wait for startup messages** (see above)

3. **Open browser to:**
   ```
   http://localhost:8888/docs
   ```

4. **You should see** the interactive API documentation page

## If Browser Still Doesn't Work

### Test with curl first:
```bash
curl http://localhost:8888/health
```

If curl works but browser doesn't:
- Try a different browser
- Clear browser cache
- Try incognito/private mode
- Check browser console (F12) for errors

### Check if server is actually running:
```bash
# Should show uvicorn process
ps aux | grep uvicorn

# Should show port 8888 in use
lsof -i :8888
```

### Common Issues:

1. **"This site can't be reached"**
   - Server isn't running or crashed
   - Check terminal for errors

2. **"Connection refused"**
   - Server didn't start properly
   - Check terminal output

3. **Page loads but shows errors**
   - Check browser console (F12)
   - Check terminal for backend errors

## Alternative: Use API Docs

The easiest way to test is using the interactive API docs:
1. Go to http://localhost:8888/docs
2. Click on any endpoint
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

This doesn't require the frontend to work!
