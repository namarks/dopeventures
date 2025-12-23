#!/usr/bin/env python3
"""
Development Server Launcher for Dopetracks

Simple launcher for development/testing. Starts uvicorn with auto-reload.
For production use or apps with setup wizard, use scripts/launch/app_launcher.py instead.
"""
import sys
import os
import subprocess
from pathlib import Path

# Check if virtual environment is active
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    # Try local venv in project root
    local_venv = Path(__file__).parent / "venv"
    if local_venv.exists():
        venv_python = local_venv / "bin" / "python3"
        if venv_python.exists():
            print("⚠️  Virtual environment not active!")
            print(f"   Activating: {local_venv}")
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    
    print("❌ Virtual environment not found and not active!")
    print("   Please activate your virtual environment first:")
    print("   source venv/bin/activate")
    print()
    print("   Or install dependencies in current environment:")
    print("   pip install -r requirements.txt")
    sys.exit(1)

# Add the packages directory to Python path
project_root = Path(__file__).parent
packages_dir = project_root / "packages"
sys.path.insert(0, str(packages_dir))

if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Suppress watchfiles INFO messages (they're just noise from file watching)
    watchfiles_logger = logging.getLogger("watchfiles")
    watchfiles_logger.setLevel(logging.WARNING)  # Only show warnings/errors, not INFO
    
    print("🚀 Starting Dopetracks Application...")
    print("📍 Health check: http://127.0.0.1:8888/health")
    print("🌐 Application: http://127.0.0.1:8888")
    print(f"✅ Virtual env: {sys.prefix}")
    print()
    
    # Import the app
    from dopetracks.app import app
    
    # Optional preflight: kill existing process on the port if requested
    kill_on_port = os.getenv("DOPETRACKS_KILL_PORT", "0") == "1"

    # Check if port is already in use
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_in_use = False
    try:
        sock.bind(("127.0.0.1", 8888))
        sock.close()
    except OSError:
        port_in_use = True

    if port_in_use and kill_on_port:
        print("⚠️  Port 8888 in use. Attempting to kill existing process (DOPETRACKS_KILL_PORT=1)...")
        try:
            # Find PIDs listening on 8888 and kill them
            result = subprocess.run(
                ["lsof", "-ti", ":8888"],
                capture_output=True,
                text=True,
                check=False,
            )
            pids = [pid for pid in result.stdout.strip().splitlines() if pid]
            if not pids:
                print("   No PIDs found on port 8888; continuing startup.")
            else:
                subprocess.run(["kill"] + pids, check=False)
                print(f"   Killed PIDs on port 8888: {', '.join(pids)}")
            # Re-check bind
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 8888))
            sock.close()
            port_in_use = False
        except Exception as e:
            print(f"   Failed to free port 8888 automatically: {e}")
            port_in_use = True

    if port_in_use:
        print(f"⚠️  Port 8888 is already in use!")
        print(f"   Another instance may be running. Try:")
        print(f"   pkill -f 'uvicorn.*app'")
        print(f"   OR")
        print(f"   lsof -ti :8888 | xargs kill -9")
        print(f"   Or set DOPETRACKS_KILL_PORT=1 to auto-kill on startup.")
        sys.exit(1)
    
    # Run the app
    uvicorn.run(
        "dopetracks.app:app",
        host="127.0.0.1",
        port=8888,
        reload=False,
        log_level="info"
    )
