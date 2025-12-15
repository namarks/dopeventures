#!/bin/bash
# Script to update SPOTIFY_REDIRECT_URI from localhost to 127.0.0.1

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found!"
    echo "Creating .env file with correct redirect URI..."
    echo "SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback" > "$ENV_FILE"
    echo "✅ Created .env file"
else
    # Check if SPOTIFY_REDIRECT_URI exists
    if grep -q "SPOTIFY_REDIRECT_URI" "$ENV_FILE"; then
        # Update existing entry
        if [[ "$OSTYPE" == "darwin"* ]]; then
            # macOS
            sed -i '' 's|SPOTIFY_REDIRECT_URI=.*|SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback|' "$ENV_FILE"
        else
            # Linux
            sed -i 's|SPOTIFY_REDIRECT_URI=.*|SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback|' "$ENV_FILE"
        fi
        echo "✅ Updated SPOTIFY_REDIRECT_URI in .env file"
    else
        # Add new entry
        echo "SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback" >> "$ENV_FILE"
        echo "✅ Added SPOTIFY_REDIRECT_URI to .env file"
    fi
fi

echo ""
echo "📋 NEXT STEPS:"
echo "1. Go to: https://developer.spotify.com/dashboard"
echo "2. Click your app → 'Edit Settings'"
echo "3. Remove: http://localhost:8888/callback (if present)"
echo "4. Add: http://127.0.0.1:8888/callback"
echo "5. Click 'Save'"
echo "6. Restart your server"
echo ""
echo "✅ Your .env file now has:"
grep "SPOTIFY_REDIRECT_URI" "$ENV_FILE"
