# Quick Start Guide

## Starting the Application

### Option 1: Direct Execution (Recommended)

```bash
# From project root directory
python3 start.py
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
python3 start.py
```

### What You Should See

```
🚀 Starting Dopetracks Application...
📍 Health check: http://127.0.0.1:8888/health
🌐 Application: http://127.0.0.1:8888
INFO:     Uvicorn running on http://127.0.0.1:8888
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
python3 start.py
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
# Or change the port in start.py
```

### Import Errors
**Solution:** Make sure you're running from the project root:
```bash
cd /path/to/dopeventures
python3 start.py
```
