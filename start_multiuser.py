#!/usr/bin/env python3
"""
Startup script for the Dopetracks multi-user application.
"""
import sys
import os
from pathlib import Path

# Add the packages directory to Python path
project_root = Path(__file__).parent
packages_dir = project_root / "packages"
sys.path.insert(0, str(packages_dir))

# Now import and run the app
if __name__ == "__main__":
    import uvicorn
    
    # Import the app
    from dopetracks.dopetracks.multiuser_app import app
    
    print("🚀 Starting Dopetracks Multi-User Application...")
    print("📍 Health check: http://localhost:8888/health")
    print("🌐 API docs: http://localhost:8888/docs")
    print("🔐 Auth endpoints: http://localhost:8888/auth/")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8888,
        reload=True,
        log_level="info"
    ) 