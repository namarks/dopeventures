#!/bin/bash
# Quick setup and run script for Dopetracks
# This script activates the virtual environment and starts the server

echo "🔍 Activating virtual environment..."

# Check for external venv (your setup)
if [ -d "/Users/nmarks/projects/venvs/dopetracks_env" ]; then
    echo "✅ Found external virtual environment"
    VENV_PATH="/Users/nmarks/projects/venvs/dopetracks_env"
# Check for local venv
elif [ -d "venv" ]; then
    echo "✅ Found local virtual environment"
    VENV_PATH="venv"
else
    echo "❌ No virtual environment found"
    echo "Creating one at: venv"
    python3 -m venv venv
    VENV_PATH="venv"
fi

echo ""
echo "🔧 Activating virtual environment: $VENV_PATH"
source "$VENV_PATH/bin/activate"

echo ""
echo "📦 Checking dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "✅ Dependencies already installed"
fi

echo ""
echo "🚀 Starting Dopetracks application..."
echo ""
python3 start.py
