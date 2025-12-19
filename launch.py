#!/usr/bin/env python3
"""
Dopetracks GUI Launcher
A simple GUI launcher that sets up and runs Dopetracks without command line.
"""
import os
import sys
import subprocess
import webbrowser
import threading
import time
from pathlib import Path

# Try to import tkinter with better error handling
TKINTER_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import scrolledtext, messagebox
    # Test if tkinter actually works (some macOS versions have issues)
    test_root = tk.Tk()
    test_root.destroy()
    TKINTER_AVAILABLE = True
except Exception as e:
    # tkinter not available or crashes
    TKINTER_AVAILABLE = False
    if __name__ == "__main__":
        print(f"⚠️  GUI launcher not available: {e}")
        print("Using simple launcher instead...")
        simple_launcher = Path(__file__).parent / "launch_simple.py"
        if simple_launcher.exists():
            subprocess.run([sys.executable, str(simple_launcher)])
        sys.exit(0)

class DopetracksLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Dopetracks Launcher")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / "venv"
        self.server_process = None
        
        self.setup_ui()
        self.check_setup()
    
    def setup_ui(self):
        # Title
        title = tk.Label(
            self.root, 
            text="🎵 Dopetracks", 
            font=("Arial", 24, "bold"),
            pady=10
        )
        title.pack()
        
        # Status area
        status_label = tk.Label(self.root, text="Status:", font=("Arial", 12, "bold"))
        status_label.pack(anchor="w", padx=20, pady=(10, 5))
        
        self.status_text = scrolledtext.ScrolledText(
            self.root, 
            height=15, 
            width=70,
            wrap=tk.WORD,
            font=("Courier", 10)
        )
        self.status_text.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)
        self.status_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.setup_btn = tk.Button(
            button_frame,
            text="Setup (First Time)",
            command=self.run_setup,
            width=20,
            height=2,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.setup_btn.pack(side=tk.LEFT, padx=5)
        
        self.launch_btn = tk.Button(
            button_frame,
            text="Launch App",
            command=self.launch_app,
            width=20,
            height=2,
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold")
        )
        self.launch_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(
            button_frame,
            text="Stop Server",
            command=self.stop_server,
            width=20,
            height=2,
            bg="#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
    
    def log(self, message):
        """Add message to status log"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.root.update()
    
    def check_setup(self):
        """Check if setup is needed"""
        self.log("Checking setup...")
        
        needs_setup = False
        
        # Check virtual environment
        if not self.venv_path.exists():
            self.log("❌ Virtual environment not found")
            needs_setup = True
        else:
            self.log("✅ Virtual environment found")
        
        # Check .env file
        env_file = self.project_root / ".env"
        if not env_file.exists():
            self.log("❌ .env file not found")
            needs_setup = True
        else:
            # Check if it has real credentials
            with open(env_file) as f:
                content = f.read()
                if "your_client_id_here" in content or "your_client_secret_here" in content:
                    self.log("⚠️  .env file needs Spotify credentials")
                    needs_setup = True
                else:
                    self.log("✅ .env file configured")
        
        # Check config.js
        config_file = self.project_root / "website" / "config.js"
        if not config_file.exists():
            self.log("❌ config.js not found")
            needs_setup = True
        else:
            self.log("✅ config.js found")
        
        if needs_setup:
            self.log("\n⚠️  Setup required. Click 'Setup (First Time)' button.")
            self.setup_btn.config(state=tk.NORMAL)
            self.launch_btn.config(state=tk.DISABLED)
        else:
            self.log("\n✅ Ready to launch!")
            self.setup_btn.config(state=tk.DISABLED)
            self.launch_btn.config(state=tk.NORMAL)
    
    def run_setup(self):
        """Run the setup script"""
        self.log("\n" + "="*50)
        self.log("Running setup...")
        
        setup_script = self.project_root / "setup.sh"
        if not setup_script.exists():
            self.log("❌ setup.sh not found!")
            return
        
        try:
            # Make executable
            os.chmod(setup_script, 0o755)
            
            # Run setup
            result = subprocess.run(
                ["bash", str(setup_script)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True
            )
            
            self.log(result.stdout)
            if result.stderr:
                self.log("Errors:\n" + result.stderr)
            
            if result.returncode == 0:
                self.log("\n✅ Setup completed!")
                messagebox.showinfo("Setup Complete", 
                    "Setup completed!\n\n"
                    "IMPORTANT: Edit the .env file and add your Spotify credentials:\n"
                    "1. Go to https://developer.spotify.com/dashboard\n"
                    "2. Create an app\n"
                    "3. Add redirect URI: http://127.0.0.1:8888/callback\n"
                    "4. Copy Client ID and Secret to .env file")
                self.check_setup()
            else:
                self.log("\n❌ Setup failed. Check errors above.")
                messagebox.showerror("Setup Failed", "Setup failed. Check the log for details.")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            messagebox.showerror("Error", f"Setup error: {e}")
    
    def launch_app(self):
        """Launch the Dopetracks app"""
        self.log("\n" + "="*50)
        self.log("Launching Dopetracks...")
        
        # Check if server is already running
        try:
            try:
                import requests
            except ImportError:
                # requests might not be installed yet, that's ok
                pass
            else:
                response = requests.get("http://127.0.0.1:8888/health", timeout=2)
                if response.status_code == 200:
                    self.log("✅ Server already running!")
                    self.open_browser()
                    return
        except:
            pass
        
        # Activate venv and start server
        python_exe = self.venv_path / "bin" / "python3"
        if not python_exe.exists():
            self.log("❌ Python not found in virtual environment!")
            messagebox.showerror("Error", "Virtual environment not set up. Run setup first.")
            return
        
        try:
            self.log("Starting server...")
            start_script = self.project_root / "start.py"
            
            # Start server in background
            self.server_process = subprocess.Popen(
                [str(python_exe), str(start_script)],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for server to start
            self.log("Waiting for server to start...")
            for i in range(10):
                time.sleep(1)
                try:
                    try:
                        import requests
                    except ImportError:
                        # If requests not available, just wait and open browser
                        if i >= 4:  # Wait at least 5 seconds
                            break
                        continue
                    response = requests.get("http://127.0.0.1:8888/health", timeout=1)
                    if response.status_code == 200:
                        self.log("✅ Server started successfully!")
                        self.launch_btn.config(state=tk.DISABLED)
                        self.stop_btn.config(state=tk.NORMAL)
                        self.open_browser()
                        return
                except:
                    self.log(f"Waiting... ({i+1}/10)")
            
            self.log("⚠️  Server may be starting. Opening browser anyway...")
            self.open_browser()
            self.launch_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            
        except Exception as e:
            self.log(f"❌ Error starting server: {e}")
            messagebox.showerror("Error", f"Failed to start server: {e}")
    
    def open_browser(self):
        """Open browser to the app"""
        self.log("Opening browser...")
        webbrowser.open("http://127.0.0.1:8888")
        self.log("✅ Browser opened!")
    
    def stop_server(self):
        """Stop the server"""
        if self.server_process:
            self.log("Stopping server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None
            self.log("✅ Server stopped")
        
        # Also try to kill any uvicorn processes
        try:
            subprocess.run(["pkill", "-f", "uvicorn.*app"], check=False)
        except:
            pass
        
        self.launch_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

def main():
    if not TKINTER_AVAILABLE:
        print("⚠️  GUI launcher is not available (tkinter issue).")
        print("\nUsing simple launcher instead...")
        print("="*50)
        # Fall back to simple launcher
        simple_launcher = Path(__file__).parent / "launch_simple.py"
        if simple_launcher.exists():
            subprocess.run([sys.executable, str(simple_launcher)])
        else:
            print("You can run the app with: python3 start.py")
        sys.exit(0)
    
    try:
        root = tk.Tk()
        app = DopetracksLauncher(root)
        root.mainloop()
    except Exception as e:
        print(f"Error launching GUI: {e}")
        print("\nFalling back to command-line mode...")
        print("You can still run the app with: python3 start.py")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

