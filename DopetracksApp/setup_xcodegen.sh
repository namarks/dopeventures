#!/bin/bash
# Setup script for XcodeGen - automatically generates Xcode project from YAML

set -e

echo "🔧 Setting up XcodeGen for automatic Xcode project generation..."
echo ""

# Check if XcodeGen is installed
if ! command -v xcodegen &> /dev/null; then
    echo "📦 Installing XcodeGen..."
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew is not installed. Please install it first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    
    # Install XcodeGen via Homebrew
    brew install xcodegen
    echo "✅ XcodeGen installed!"
else
    echo "✅ XcodeGen is already installed"
fi

echo ""
echo "📝 Generating Xcode project from project.yml..."
xcodegen generate

echo ""
echo "✅ Done! Your Xcode project has been generated."
echo ""
echo "📋 Next steps:"
echo "   1. Open DopetracksApp.xcodeproj in Xcode"
echo "   2. All Swift files should now be automatically included"
echo ""
echo "🔄 To regenerate the project after adding new files:"
echo "   Run: xcodegen generate"
echo "   Or: ./setup_xcodegen.sh"

