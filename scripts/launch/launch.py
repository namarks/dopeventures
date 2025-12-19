#!/usr/bin/env python3
"""
Dopetracks Launcher
Simple CLI launcher that checks setup and launches the app.
"""
import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

# Check if running as bundled app (PyInstaller)
if getattr(sys, 'frozen', False):
    print("⚠️  This launcher is for development mode only.")
    print("   For bundled app, use scripts/launch/launch_bundled.py")
    sys.exit(1)

project_root = Path(__file__).parent
venv_path = project_root / "venv"
env_file = project_root / ".env"
config_file = project_root / "website" / "config.js"
start_script = project_root / "start.py"

def check_setup():
    """Check if setup is needed. Returns (needs_setup, messages)."""
    messages = []
    needs_setup = False
    
    if not venv_path.exists():
        messages.append("❌ Virtual environment not found")
        needs_setup = True
    else:
        messages.append("✅ Virtual environment found")
    
    if not env_file.exists():
        messages.append("❌ .env file not found")
        needs_setup = True
    else:
        try:
            with open(env_file) as f:
                content = f.read()
                if "your_client_id_here" in content or "your_client_secret_here" in content:
                    messages.append("⚠️  .env file needs Spotify credentials")
                    needs_setup = True
                else:
                    messages.append("✅ .env file configured")
        except Exception as e:
            messages.append(f"⚠️  Error reading .env: {e}")
            needs_setup = True
    
    if not config_file.exists():
        messages.append("❌ config.js not found")
        needs_setup = True
    else:
        messages.append("✅ config.js found")
    
    return needs_setup, messages

def run_setup():
    """Run the setup script. Returns (success, output)."""
    setup_script = project_root / "setup.sh"
    if not setup_script.exists():
        return False, "setup.sh not found!"
    
    try:
        os.chmod(setup_script, 0o755)
        result = subprocess.run(
            ["bash", str(setup_script)],
            cwd=str(project_root),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr or result.stdout
    except Exception as e:
        return False, str(e)

def check_server_running():
    """Check if server is already running."""
    try:
        import requests
        response = requests.get("http://127.0.0.1:8888/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def launch_app():
    """Launch the Dopetracks app."""
    if check_server_running():
        print("✅ Server already running!")
        webbrowser.open("http://127.0.0.1:8888")
        return
    
    python_exe = venv_path / "bin" / "python3"
    if not python_exe.exists():
        print("❌ Python not found in virtual environment!")
        print("Run setup first: python3 scripts/launch/launch.py --setup")
        sys.exit(1)
    
    print("Starting server...")
    print("(Press Ctrl+C to stop)")
    print("\nServer will open in your browser automatically...")
    print("="*50)
    
    try:
        # Start server in foreground
        subprocess.run([str(python_exe), str(start_script)], cwd=str(project_root))
    except KeyboardInterrupt:
        print("\n\nStopping server...")
        subprocess.run(["pkill", "-f", "uvicorn.*app"], check=False)
        print("✅ Server stopped")

def main():
    """Main entry point."""
    print("🎵 Dopetracks Launcher")
    print("="*50)
    
    needs_setup, messages = check_setup()
    
    for msg in messages:
        print(msg)
    
    if "--setup" in sys.argv or needs_setup:
        if needs_setup:
            print("\n" + "="*50)
            print("Running setup...")
            
            success, output = run_setup()
            
            if success:
                print("\n✅ Setup completed!")
                print("\n⚠️  IMPORTANT: Edit the .env file and add your Spotify credentials:")
                print("   1. Go to https://developer.spotify.com/dashboard")
                print("   2. Create an app")
                print("   3. Add redirect URI: http://127.0.0.1:8888/callback")
                print("   4. Copy Client ID and Secret to .env file")
                if "--setup" not in sys.argv:
                    print("\n✅ Setup complete! Run again to launch the app.")
            else:
                print(f"\n❌ Setup failed: {output}")
                sys.exit(1)
        else:
            print("\n✅ Ready to launch!")
    else:
        print("\n✅ Ready to launch!")
    
    if "--setup" not in sys.argv:
        input("\nPress Enter to launch Dopetracks (or Ctrl+C to cancel)...")
        launch_app()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
