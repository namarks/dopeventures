# Troubleshooting Guide

## Server Not Starting / API Not Responding

### Issue: Server appears to start but Swift app can't connect

**Check 1: Is the server actually running?**

Look for this in the terminal output or logs:
```
INFO:     Uvicorn running on http://127.0.0.1:8888 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

If you don't see "Uvicorn running on...", the server didn't start properly.

**Check 2: Test the API with curl**

Test the API directly:
```bash
curl http://127.0.0.1:8888/health
```

This should return `{"status":"ok"}`. If it doesn't, the server isn't running correctly.

**Check 3: Port conflicts**

Make sure nothing else is using port 8888:
```bash
lsof -i :8888
```

If something is using it, kill it:
```bash
pkill -f uvicorn
# Or kill the specific process ID shown by lsof
```

**Check 4: Swift app connection**

The Swift app connects to `http://127.0.0.1:8888`. Make sure:
- The backend server is running
- The Swift app is configured to use the correct URL
- No firewall is blocking localhost connections

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
2. **Check Swift app logs** - Look in Xcode console for connection errors
3. **Check firewall settings** - macOS might be blocking connections
4. **Restart the server** - Stop (Ctrl+C) and start again
5. **Restart the Swift app** - Quit and relaunch the app

### Getting Help

If nothing works, check:
1. Terminal output for backend errors
2. Xcode console for Swift app errors
3. Backend log file: `~/.dopetracks/logs/backend.log` or `backend.log` in project root
4. Make sure virtual environment is activated (if running in development)
5. Make sure all dependencies are installed: `pip install -r requirements.txt`
