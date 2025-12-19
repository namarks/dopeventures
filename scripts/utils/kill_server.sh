#!/bin/bash
# Script to kill any running Dopetracks server processes

echo "🔍 Looking for running server processes..."

# Find processes using port 8888
PID=$(lsof -ti:8888 2>/dev/null)

if [ -z "$PID" ]; then
    echo "✅ No process found on port 8888"
else
    echo "⚠️  Found process(es) using port 8888: $PID"
    echo "🛑 Killing process(es)..."
    kill -9 $PID 2>/dev/null
    echo "✅ Process killed"
fi

# Also kill any uvicorn processes
UVICORN_PIDS=$(pgrep -f "uvicorn.*app" 2>/dev/null)
if [ ! -z "$UVICORN_PIDS" ]; then
    echo "⚠️  Found uvicorn processes: $UVICORN_PIDS"
    kill -9 $UVICORN_PIDS 2>/dev/null
    echo "✅ Uvicorn processes killed"
fi

# Wait a moment for ports to be released
sleep 1

echo ""
echo "✅ Port 8888 should now be free"
echo "   You can now run: python3 start.py"
