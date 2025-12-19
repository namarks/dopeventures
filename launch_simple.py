#!/usr/bin/env python3
"""
Simple Dopetracks Launcher (No GUI)
A command-line launcher that sets up and runs Dopetracks.
"""
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def check_setup():
    """Check if setup is needed"""
    project_root = Path(__file__).parent
    venv_path = project_root / "venv"
    env_file = project_root / ".env"
    config_file = project_root / "website" / "config.js"
    
    needs_setup = False
    
    print("🔍 Checking setup...")
    
    if not venv_path.exists():
        print("❌ Virtual environment not found")
        needs_setup = True
    else:
        print("✅ Virtual environment found")
    
    if not env_file.exists():
        print("❌ .env file not found")
        needs_setup = True
    else:
        with open(env_file) as f:
            content = f.read()
            if "your_client_id_here" in content or "your_client_secret_here" in content:
                print("⚠️  .env file needs Spotify credentials")
                needs_setup = True
            else:
                print("✅ .env file configured")
    
    if not config_file.exists():
        print("❌ config.js not found")
        needs_setup = True
    else:
        print("✅ config.js found")
    
    return needs_setup, project_root, venv_path

def run_setup(project_root):
    """Run the setup script"""
    print("\n" + "="*50)
    print("Running setup...")
    
    setup_script = project_root / "setup.sh"
    if not setup_script.exists():
        print("❌ setup.sh not found!")
        return False
    
    try:
        os.chmod(setup_script, 0o755)
        result = subprocess.run(
            ["bash", str(setup_script)],
            cwd=str(project_root),
            text=True
        )
        
        if result.returncode == 0:
            print("\n✅ Setup completed!")
            print("\n⚠️  IMPORTANT: Edit the .env file and add your Spotify credentials:")
            print("   1. Go to https://developer.spotify.com/dashboard")
            print("   2. Create an app")
            print("   3. Add redirect URI: http://127.0.0.1:8888/callback")
            print("   4. Copy Client ID and Secret to .env file")
            return True
        else:
            print("\n❌ Setup failed")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def launch_app(project_root, venv_path):
    """Launch the Dopetracks app"""
    print("\n" + "="*50)
    print("Launching Dopetracks...")
    
    # Check if server is already running
    try:
        import requests
        response = requests.get("http://127.0.0.1:8888/health", timeout=2)
        if response.status_code == 200:
            print("✅ Server already running!")
            print("Opening browser...")
            webbrowser.open("http://127.0.0.1:8888")
            return
    except:
        pass
    
    # Start server
    python_exe = venv_path / "bin" / "python3"
    if not python_exe.exists():
        print("❌ Python not found in virtual environment!")
        print("Run setup first: python3 launch_simple.py --setup")
        return
    
    start_script = project_root / "start.py"
    
    print("Starting server...")
    print("(Press Ctrl+C to stop)")
    print("\nServer will open in your browser automatically...")
    print("="*50)
    
    # Start server in foreground
    try:
        subprocess.run([str(python_exe), str(start_script)], cwd=str(project_root))
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        subprocess.run(["pkill", "-f", "uvicorn.*app"], check=False)
        print("✅ Server stopped")

def main():
    print("🎵 Dopetracks Launcher")
    print("="*50)
    
    needs_setup, project_root, venv_path = check_setup()
    
    if "--setup" in sys.argv or needs_setup:
        if run_setup(project_root):
            print("\n✅ Setup complete! Run again to launch the app.")
        else:
            print("\n❌ Setup failed. Please check errors above.")
            sys.exit(1)
    else:
        print("\n✅ Ready to launch!")
        input("\nPress Enter to launch Dopetracks (or Ctrl+C to cancel)...")
        launch_app(project_root, venv_path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

