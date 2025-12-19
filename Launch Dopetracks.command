#!/bin/bash
# Dopetracks Launcher - Double-click to launch
# This file can be double-clicked on macOS to launch Dopetracks

cd "$(dirname "$0")"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    osascript -e 'display dialog "Python 3 is not installed. Please install Python 3.11 or higher." buttons {"OK"} default button "OK"'
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    osascript -e 'display dialog "Virtual environment not found. Running setup first..." buttons {"OK"} default button "OK"'
    ./setup.sh
fi

# Activate virtual environment and launch
source venv/bin/activate

# Try GUI launcher, automatically falls back to simple launcher if GUI fails
python3 launch_simple.py

