#!/bin/bash
# Helper script to verify which files need to be added to Xcode project

echo "📋 Files that need to be added to Xcode project:"
echo ""
echo "Models folder:"
ls -1 App/Models/*.swift 2>/dev/null | sed 's/^/  - /'
echo ""
echo "Services folder:"
ls -1 App/Services/*.swift 2>/dev/null | sed 's/^/  - /'
echo ""
echo "Views folder:"
ls -1 App/Views/*.swift 2>/dev/null | sed 's/^/  - /'
echo ""
echo "Root level files:"
ls -1 App/*.swift 2>/dev/null | sed 's/^/  - /'
echo ""
echo "✅ To add these files in Xcode:"
echo "   1. Right-click 'DopetracksApp' group in Project Navigator"
echo "   2. Select 'Add Files to DopetracksApp...'"
echo "   3. Select the Models, Services, Views folders AND DopetracksApp.swift, ContentView.swift"
echo "   4. Uncheck 'Copy items if needed'"
echo "   5. Check 'Create groups'"
echo "   6. Check 'Add to targets: DopetracksApp'"
echo "   7. Click Add"

