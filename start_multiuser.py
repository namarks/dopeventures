#!/usr/bin/env python3
"""
Startup script for the Dopetracks multi-user application.
"""
import sys
import os
from pathlib import Path

# Check if virtual environment is active
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    venv_path = Path("/Users/nmarks/root_code_repo/venvs/dopetracks_env")
    if venv_path.exists():
        print("⚠️  Virtual environment not active!")
        print(f"   Activating: {venv_path}")
        print("   (Or run: source /Users/nmarks/root_code_repo/venvs/dopetracks_env/bin/activate)")
        # Try to activate programmatically (won't work in all shells, but worth trying)
        venv_python = venv_path / "bin" / "python3"
        if venv_python.exists():
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    else:
        print("❌ Virtual environment not found and not active!")
        print("   Please activate your virtual environment first:")
        print("   source /path/to/venv/bin/activate")
        sys.exit(1)

# Add the packages directory to Python path
project_root = Path(__file__).parent
packages_dir = project_root / "packages"
sys.path.insert(0, str(packages_dir))

# Now import and run the app
if __name__ == "__main__":
    import uvicorn
    
    # Import the app
    from dopetracks.multiuser_app import app
    
    print("🚀 Starting Dopetracks Multi-User Application...")
    print("📍 Health check: http://127.0.0.1:8888/health")
    print("🌐 API docs: http://127.0.0.1:8888/docs")
    print("🔐 Auth endpoints: http://127.0.0.1:8888/auth/")
    print(f"✅ Virtual env: {sys.prefix}")
    
    # Use import string for reload to work properly
    uvicorn.run(
        "dopetracks.multiuser_app:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="info"
    ) 