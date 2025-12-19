#!/usr/bin/env python3
"""
Dopetracks Launcher Wrapper
Tries GUI launcher first, falls back to simple launcher if GUI fails.
"""
import sys
import subprocess
from pathlib import Path

def main():
    project_root = Path(__file__).parent
    
    # Try GUI launcher first
    gui_launcher = project_root / "launch.py"
    simple_launcher = project_root / "launch_simple.py"
    
    if gui_launcher.exists():
        # Try to run GUI launcher
        result = subprocess.run(
            [sys.executable, str(gui_launcher)],
            capture_output=True,
            text=True,
            timeout=5  # If it crashes immediately, timeout quickly
        )
        
        # If it succeeded or is still running, we're good
        if result.returncode == 0:
            return
    
    # Fall back to simple launcher
    print("Using simple launcher (GUI not available)...")
    if simple_launcher.exists():
        subprocess.run([sys.executable, str(simple_launcher)])
    else:
        print("Error: No launcher found!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

