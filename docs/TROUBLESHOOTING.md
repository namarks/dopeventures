# Troubleshooting Guide

## Server Not Starting / Browser Links Not Working

### Issue: Server appears to start but browser can't connect

**Check 1: Is the server actually running?**

Look for this in the terminal output:
```
INFO:     Uvicorn running on http://0.0.0.0:8888 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

If you don't see "Uvicorn running on...", the server didn't start properly.

**Check 2: Try these URLs**

The backend API runs on port 8888. Try these URLs:

1. **Health Check** (should always work):
   ```
   http://localhost:8888/health
   ```

2. **API Documentation** (interactive):
   ```
   http://localhost:8888/docs
   ```

3. **Root endpoint**:
   ```
   http://localhost:8888/
   ```

**Check 3: Test with curl first**

Before trying the browser, test with curl:
```bash
curl http://localhost:8888/health
```

If curl works but browser doesn't, it might be a browser/CORS issue.

**Check 4: Port conflicts**

Make sure nothing else is using port 8888:
```bash
lsof -i :8888
```

If something is using it, kill it:
```bash
pkill -f uvicorn
# Or kill the specific process ID shown by lsof
```

### Issue: "Website directory not found" warning

This is just a warning - the API still works. The frontend files are in `website/` but the app is looking for them in a different location.

**Solution:** The API endpoints still work. Access them via:
- http://localhost:8888/docs (API documentation)
- http://localhost:8888/health (health check)

Or serve the frontend separately:
```bash
cd website
python3 -m http.server 8889
```

Then access frontend at: http://localhost:8889

### Issue: "You must pass the application as an import string" warning

This is fixed in the latest version. If you see it, the server should still work, but reload might not.

**Solution:** The warning is harmless, but you can restart the server to clear it.

### Issue: Connection refused / Can't connect

**Possible causes:**

1. **Server not started** - Make sure you see "Uvicorn running on..." in terminal
2. **Wrong port** - Make sure you're using port 8888
3. **Firewall** - Check if firewall is blocking the connection
4. **Virtual env not activated** - Make sure venv is active (you should see `(dopetracks_env)` in prompt)

### Issue: 404 Not Found

**Check the URL:**
- ✅ Correct: `http://localhost:8888/health`
- ❌ Wrong: `http://localhost:8888/health/` (trailing slash might matter)
- ❌ Wrong: `http://127.0.0.1:8888/health` (use localhost)

### Issue: 500 Internal Server Error

Check the terminal for error messages. Common causes:
- Database not initialized
- Missing environment variables
- Import errors

### Quick Diagnostic Commands

```bash
# 1. Check if server is running
curl http://localhost:8888/health

# 2. Check what's on port 8888
lsof -i :8888

# 3. Check if virtual env is active
echo $VIRTUAL_ENV
which python3

# 4. Test if dependencies are installed
python3 -c "import fastapi; import sqlalchemy; print('OK')"
```

### Still Not Working?

1. **Check terminal output** - Look for error messages
2. **Try a different browser** - Sometimes browser cache causes issues
3. **Check firewall settings** - macOS might be blocking connections
4. **Restart the server** - Stop (Ctrl+C) and start again

### Getting Help

If nothing works, check:
1. Terminal output for errors
2. Browser console (F12) for errors
3. Make sure virtual environment is activated
4. Make sure all dependencies are installed: `pip install -r requirements.txt`
