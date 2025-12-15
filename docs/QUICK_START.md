# Quick Start Guide

## Starting the Application

### Option 1: Direct Execution (Recommended)

```bash
# From project root directory
python3 start_multiuser.py
```

**Note:** On macOS, use `python3` not `python`

### Option 2: With Virtual Environment

If you're using a virtual environment:

```bash
# Activate virtual environment first
source venv/bin/activate
# OR if using external venv:
# source /path/to/your/venv/bin/activate

# Then run
python3 start_multiuser.py
```

### What You Should See

```
🚀 Starting Dopetracks Multi-User Application...
📍 Health check: http://localhost:8888/health
🌐 API docs: http://localhost:8888/docs
🔐 Auth endpoints: http://localhost:8888/auth/
INFO:     Uvicorn running on http://0.0.0.0:8888
```

### Verify It's Working

Open in browser:
- **Health Check**: http://localhost:8888/health
- **API Docs**: http://localhost:8888/docs

Or test with curl:
```bash
curl http://localhost:8888/health
```

## Troubleshooting

### "command not found: python"
**Solution:** Use `python3` instead:
```bash
python3 start_multiuser.py
```

### "No module named 'dopetracks'"
**Solution:** Make sure you're in the project root directory and packages are installed:
```bash
pip3 install -r requirements.txt
```

### "Port already in use"
**Solution:** Kill the existing process:
```bash
pkill -f uvicorn
# Or change the port in start_multiuser.py
```

### Import Errors
**Solution:** Make sure you're running from the project root:
```bash
cd /path/to/dopeventures
python3 start_multiuser.py
```
