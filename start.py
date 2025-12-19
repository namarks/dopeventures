#!/usr/bin/env python3
"""
Startup script for Dopetracks local application (single-user, no authentication).
Each user runs this on their own MacBook for privacy.
"""
import sys
import os
from pathlib import Path

# Check if virtual environment is active
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    # Try to find and activate virtual environment
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
        # Try local venv
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
        print("   OR")
        print("   source /Users/nmarks/root_code_repo/venvs/dopetracks_env/bin/activate")
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
    
    print("🚀 Starting Dopetracks Application...")
    print("📍 Health check: http://127.0.0.1:8888/health")
    print("🌐 Application: http://127.0.0.1:8888")
    print(f"✅ Virtual env: {sys.prefix}")
    print()
    
    # Import the app
    from dopetracks.app import app
    
    # Run the app
    uvicorn.run(
        "dopetracks.app:app",
        host="127.0.0.1",
        port=8888,
        reload=True,
        log_level="info"
    )
