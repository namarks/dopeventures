#!/bin/bash
# Script to ensure server is fully restarted with new environment variables

echo "🛑 Stopping any running server processes..."
pkill -f "uvicorn.*app" || echo "No server process found"

echo ""
echo "⏳ Waiting 2 seconds for processes to stop..."
sleep 2

echo ""
echo "✅ Verifying .env file..."
if grep -q "SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback" .env; then
    echo "   ✅ .env has correct redirect URI: http://127.0.0.1:8888/callback"
else
    echo "   ❌ .env does NOT have correct redirect URI!"
    echo "   Current value:"
    grep "SPOTIFY_REDIRECT_URI" .env || echo "   SPOTIFY_REDIRECT_URI not found in .env"
    exit 1
fi

echo ""
echo "🚀 Starting server with new configuration..."
echo "   (Make sure you're in the project root directory)"
echo ""
python3 dev_server.py
