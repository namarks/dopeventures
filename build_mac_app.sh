#!/bin/bash
# Build macOS app bundle for Dopetracks
# This script packages the application using PyInstaller

set -e  # Exit on error

echo "🔨 Building Dopetracks macOS App..."
echo "===================================="
echo ""

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Error: This script must be run on macOS"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Warning: Virtual environment not active"
    echo "   Activating local venv..."
    if [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "❌ Error: Virtual environment not found. Run setup.sh first."
        exit 1
    fi
fi

# Install PyInstaller if needed
echo "📦 Checking PyInstaller..."
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "   Installing PyInstaller..."
    pip install pyinstaller --quiet
fi

# Clean previous builds
echo ""
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ *.spec.bak

# Build app
echo ""
echo "🔨 Building app bundle (this may take a few minutes)..."
pyinstaller build_app.spec --clean --noconfirm

# Check if build succeeded
if [ ! -d "dist/Dopetracks.app" ]; then
    echo "❌ Error: Build failed - Dopetracks.app not found"
    exit 1
fi

echo ""
echo "✅ Build complete!"
echo ""
echo "📦 App bundle: dist/Dopetracks.app"
echo ""

# Ask if user wants to create DMG
read -p "Create DMG file? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "📦 Creating DMG..."
    
    # Create DMG directory
    DMG_DIR="dist/dmg"
    rm -rf "$DMG_DIR"
    mkdir -p "$DMG_DIR"
    
    # Copy app to DMG directory
    cp -R "dist/Dopetracks.app" "$DMG_DIR/"
    
    # Create DMG
    DMG_NAME="Dopetracks.dmg"
    hdiutil create -volname "Dopetracks" \
        -srcfolder "$DMG_DIR" \
        -ov -format UDZO \
        "dist/$DMG_NAME"
    
    echo ""
    echo "✅ DMG created: dist/$DMG_NAME"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Test the app: open dist/Dopetracks.app"
    echo "   2. Code sign (optional): codesign --deep --force --verify --verbose --sign \"Developer ID Application: Your Name\" dist/Dopetracks.app"
    echo "   3. Notarize (optional): xcrun notarytool submit dist/Dopetracks.dmg --apple-id your@email.com --team-id YOUR_TEAM_ID --password YOUR_APP_PASSWORD"
else
    echo ""
    echo "📝 To create DMG later, run:"
    echo "   hdiutil create -volname \"Dopetracks\" -srcfolder dist/Dopetracks.app -ov -format UDZO dist/Dopetracks.dmg"
fi

echo ""
echo "✨ Done!"

