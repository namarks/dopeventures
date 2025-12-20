#!/bin/bash
# Dopetracks Setup Script
# This script helps you set up the Dopetracks application quickly

set -e  # Exit on error

echo "🎵 Dopetracks Setup"
echo "=================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Found Python $PYTHON_VERSION"

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  Warning: This app is designed for macOS (requires Messages database access)"
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# Check for .env file
echo ""
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file template..."
    cat > .env << EOF
# Spotify API Credentials
# Get these from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Optional: Database URL (defaults to ~/.dopetracks/local.db)
# DATABASE_URL=sqlite:///path/to/your/database.db
EOF
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file and add your Spotify credentials!"
    echo "   1. Go to https://developer.spotify.com/dashboard"
    echo "   2. Create a new app"
    echo "   3. Add redirect URI: http://127.0.0.1:8888/callback"
    echo "   4. Copy Client ID and Client Secret to .env file"
else
    echo "✅ .env file already exists"
fi

# Note: Native macOS app - no website config needed

# Check macOS permissions
echo ""
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🔐 macOS Permissions Check"
    echo "   To access your Messages database, you need to grant Full Disk Access:"
    echo "   1. Open System Preferences → Security & Privacy → Privacy"
    echo "   2. Select 'Full Disk Access'"
    echo "   3. Click the lock and enter your password"
    echo "   4. Add Terminal (or Python) to the list"
    echo ""
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your Spotify credentials"
echo "2. For development: Run 'python3 dev_server.py' to start the API server"
echo "3. For native app: Open DopetracksApp/DopetracksApp.xcodeproj in Xcode and run"
echo ""
echo "For more help, see README.md"

