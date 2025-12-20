#!/bin/bash
# Regenerate Xcode project from scratch using XcodeGen

set -e

cd "$(dirname "$0")"

echo "🧹 Cleaning up existing Xcode project..."
if [ -d "DopetracksApp/DopetracksApp.xcodeproj" ]; then
    # Backup existing project (just in case)
    BACKUP_NAME="DopetracksApp.xcodeproj.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up to: $BACKUP_NAME"
    mv "DopetracksApp/DopetracksApp.xcodeproj" "DopetracksApp/$BACKUP_NAME" 2>/dev/null || true
    echo "✅ Backed up existing project"
fi

echo ""
echo "🔧 Checking XcodeGen installation..."
if ! command -v xcodegen &> /dev/null; then
    echo "📦 Installing XcodeGen..."
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew is not installed. Please install it first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install xcodegen
else
    echo "✅ XcodeGen is installed"
fi

echo ""
echo "📝 Generating Xcode project from project.yml..."
xcodegen generate

if [ -f "DopetracksApp.xcodeproj/project.pbxproj" ]; then
    echo ""
    echo "✅ Success! Xcode project generated at: DopetracksApp.xcodeproj"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Open the project: open DopetracksApp.xcodeproj"
    echo "   2. Verify all Swift files are included in the Project Navigator"
    echo "   3. Build and run (Cmd+R)"
    echo ""
    echo "🔄 To regenerate in the future, just run: ./regenerate_project.sh"
else
    echo ""
    echo "❌ Error: Project file not generated. Check project.yml for errors."
    exit 1
fi

