#!/usr/bin/env python3
"""
App Launcher for Dopetracks - Native macOS App

Full-featured launcher that handles:
- First-time setup wizard (web-based, for initial configuration)
- Bundled app support (PyInstaller)
- API server startup

This is the main launcher used by the Swift native macOS app.
The Swift app handles all UI - this launcher just starts the API server.
For simple development, use dev_server.py instead.
"""
import sys
import os
from pathlib import Path
import threading
import time
import uvicorn
import logging

# Determine if running as bundled app
if getattr(sys, 'frozen', False):
    # Running as bundled executable (PyInstaller)
    APP_DIR = Path(sys._MEIPASS)  # PyInstaller temp directory
    BASE_DIR = Path(os.path.expanduser('~'))
    IS_BUNDLED = True
else:
    # Running as script (development)
    APP_DIR = Path(__file__).parent
    BASE_DIR = APP_DIR
    IS_BUNDLED = False

# User data directory (persistent across app updates)
USER_DATA_DIR = BASE_DIR / 'Library' / 'Application Support' / 'Dopetracks'
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = USER_DATA_DIR / '.env'
DATABASE_DIR = USER_DATA_DIR
LOG_DIR = BASE_DIR / 'Library' / 'Logs' / 'Dopetracks'
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "launcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_setup_complete():
    """Check if app is fully configured."""
    if not CONFIG_FILE.exists():
        logger.info("Config file not found - setup required")
        return False
    
    # Check if config has real credentials
    try:
        with open(CONFIG_FILE) as f:
            content = f.read()
            if 'your_client_id_here' in content or not content.strip():
                logger.info("Config file has placeholder values - setup required")
                return False
        
        # Validate Spotify credentials are present
        env_vars = {}
        for line in content.split('\n'):
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
        
        has_client_id = bool(env_vars.get('SPOTIFY_CLIENT_ID') and 
                           env_vars.get('SPOTIFY_CLIENT_ID') != 'your_client_id_here')
        has_client_secret = bool(env_vars.get('SPOTIFY_CLIENT_SECRET') and 
                               env_vars.get('SPOTIFY_CLIENT_SECRET') != 'your_client_secret_here')
        
        if not (has_client_id and has_client_secret):
            logger.info("Config file missing Spotify credentials - setup required")
            return False
        
        logger.info("Setup complete - config file has valid credentials")
        return True
    except Exception as e:
        logger.error(f"Error checking config: {e}")
        return False

def launch_setup_wizard():
    """Launch setup wizard web interface."""
    logger.info("Launching setup wizard...")
    
    # Import here to avoid issues if dependencies aren't available
    try:
        from fastapi import FastAPI, Request, Form
        from fastapi.responses import HTMLResponse, RedirectResponse
        import httpx
    except ImportError as e:
        logger.error(f"Missing dependencies for setup wizard: {e}")
        print("❌ Error: Missing required dependencies. Please install requirements.txt")
        sys.exit(1)
    
    setup_app = FastAPI(title="Dopetracks Setup")
    
    @setup_app.get("/", response_class=HTMLResponse)
    async def setup_wizard_home():
        """Setup wizard HTML page."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dopetracks Setup</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                }
                .container {
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 600px;
                    width: 100%;
                    padding: 40px;
                }
                h1 {
                    color: #333;
                    margin-bottom: 10px;
                    font-size: 32px;
                }
                .subtitle {
                    color: #666;
                    margin-bottom: 30px;
                    font-size: 16px;
                }
                .step {
                    display: none;
                }
                .step.active {
                    display: block;
                }
                .form-group {
                    margin-bottom: 20px;
                }
                label {
                    display: block;
                    margin-bottom: 8px;
                    color: #333;
                    font-weight: 500;
                }
                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 12px;
                    border: 2px solid #e0e0e0;
                    border-radius: 6px;
                    font-size: 14px;
                    transition: border-color 0.3s;
                }
                input:focus {
                    outline: none;
                    border-color: #667eea;
                }
                .button {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.3s;
                    width: 100%;
                    margin-top: 10px;
                }
                .button:hover {
                    background: #5568d3;
                }
                .button:disabled {
                    background: #ccc;
                    cursor: not-allowed;
                }
                .button-secondary {
                    background: #6c757d;
                }
                .button-secondary:hover {
                    background: #5a6268;
                }
                .info-box {
                    background: #e7f3ff;
                    border-left: 4px solid #2196F3;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }
                .error-box {
                    background: #ffe7e7;
                    border-left: 4px solid #f44336;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    color: #c62828;
                    display: none;
                }
                .success-box {
                    background: #e8f5e9;
                    border-left: 4px solid #4caf50;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    color: #2e7d32;
                    display: none;
                }
                .step-indicator {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 30px;
                }
                .step-dot {
                    width: 30px;
                    height: 30px;
                    border-radius: 50%;
                    background: #e0e0e0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #999;
                    font-weight: bold;
                }
                .step-dot.active {
                    background: #667eea;
                    color: white;
                }
                .step-dot.complete {
                    background: #4caf50;
                    color: white;
                }
                .link {
                    color: #667eea;
                    text-decoration: none;
                }
                .link:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎵 Dopetracks Setup</h1>
                <p class="subtitle">Let's get you set up in a few simple steps</p>
                
                <div class="step-indicator">
                    <div class="step-dot active" id="dot-1">1</div>
                    <div class="step-dot" id="dot-2">2</div>
                    <div class="step-dot" id="dot-3">3</div>
                    <div class="step-dot" id="dot-4">4</div>
                </div>
                
                <div class="error-box" id="error-box"></div>
                <div class="success-box" id="success-box"></div>
                
                <!-- Step 1: Welcome -->
                <div class="step active" id="step-1">
                    <h2>Welcome to Dopetracks!</h2>
                    <p style="margin: 20px 0;">Dopetracks creates Spotify playlists from songs shared in your iMessage chats.</p>
                    <div class="info-box">
                        <strong>What you'll need:</strong>
                        <ul style="margin-top: 10px; margin-left: 20px;">
                            <li>A Spotify Premium account</li>
                            <li>A Spotify Developer App (free, 2-minute setup)</li>
                            <li>Full Disk Access permission (for Messages database)</li>
                        </ul>
                    </div>
                    <button class="button" onclick="nextStep()">Get Started</button>
                </div>
                
                <!-- Step 2: Spotify Setup Instructions -->
                <div class="step" id="step-2">
                    <h2>Create Spotify Developer App</h2>
                    <p style="margin: 20px 0;">First, you need to create a free Spotify Developer App:</p>
                    <ol style="margin-left: 20px; margin-bottom: 20px;">
                        <li style="margin-bottom: 10px;">Go to <a href="https://developer.spotify.com/dashboard" target="_blank" class="link">Spotify Developer Dashboard</a></li>
                        <li style="margin-bottom: 10px;">Click "Create an app"</li>
                        <li style="margin-bottom: 10px;">Fill in app name and description (anything works)</li>
                        <li style="margin-bottom: 10px;">Check "I understand and agree..." checkbox</li>
                        <li style="margin-bottom: 10px;">Click "Save"</li>
                        <li style="margin-bottom: 10px;">Click "Edit Settings"</li>
                        <li style="margin-bottom: 10px;">Under "Redirect URIs", add: <code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">http://127.0.0.1:8888/callback</code></li>
                        <li style="margin-bottom: 10px;">Click "Add" then "Save"</li>
                        <li style="margin-bottom: 10px;">Copy your "Client ID" and "Client Secret"</li>
                    </ol>
                    <div class="info-box">
                        <strong>Note:</strong> The redirect URI must be exactly <code>http://127.0.0.1:8888/callback</code> (not localhost!)
                    </div>
                    <button class="button" onclick="nextStep()">I've Created My App</button>
                    <button class="button button-secondary" onclick="prevStep()">Back</button>
                </div>
                
                <!-- Step 3: Enter Credentials -->
                <div class="step" id="step-3">
                    <h2>Enter Spotify Credentials</h2>
                    <form id="credentials-form" onsubmit="testCredentials(event)">
                        <div class="form-group">
                            <label for="client-id">Client ID</label>
                            <input type="text" id="client-id" name="client_id" required placeholder="Enter your Spotify Client ID">
                        </div>
                        <div class="form-group">
                            <label for="client-secret">Client Secret</label>
                            <input type="password" id="client-secret" name="client_secret" required placeholder="Enter your Spotify Client Secret">
                        </div>
                        <button type="submit" class="button" id="test-button">Test & Save</button>
                        <button type="button" class="button button-secondary" onclick="prevStep()">Back</button>
                    </form>
                </div>
                
                <!-- Step 4: Complete -->
                <div class="step" id="step-4">
                    <h2>✅ Setup Complete!</h2>
                    <p style="margin: 20px 0;">Your Spotify credentials have been saved. The app will now launch.</p>
                    <div class="info-box">
                        <strong>Next Steps:</strong>
                        <ul style="margin-top: 10px; margin-left: 20px;">
                            <li>Grant Full Disk Access in System Preferences (if prompted)</li>
                            <li>Start creating playlists from your iMessage chats!</li>
                        </ul>
                    </div>
                    <button class="button" onclick="launchApp()">Launch Dopetracks</button>
                </div>
            </div>
            
            <script>
                let currentStep = 1;
                const totalSteps = 4;
                
                function showError(message) {
                    const errorBox = document.getElementById('error-box');
                    errorBox.textContent = message;
                    errorBox.style.display = 'block';
                    document.getElementById('success-box').style.display = 'none';
                }
                
                function showSuccess(message) {
                    const successBox = document.getElementById('success-box');
                    successBox.textContent = message;
                    successBox.style.display = 'block';
                    document.getElementById('error-box').style.display = 'none';
                }
                
                function updateStepIndicator() {
                    for (let i = 1; i <= totalSteps; i++) {
                        const dot = document.getElementById(`dot-${i}`);
                        dot.classList.remove('active', 'complete');
                        if (i < currentStep) {
                            dot.classList.add('complete');
                        } else if (i === currentStep) {
                            dot.classList.add('active');
                        }
                    }
                }
                
                function nextStep() {
                    if (currentStep < totalSteps) {
                        document.getElementById(`step-${currentStep}`).classList.remove('active');
                        currentStep++;
                        document.getElementById(`step-${currentStep}`).classList.add('active');
                        updateStepIndicator();
                    }
                }
                
                function prevStep() {
                    if (currentStep > 1) {
                        document.getElementById(`step-${currentStep}`).classList.remove('active');
                        currentStep--;
                        document.getElementById(`step-${currentStep}`).classList.add('active');
                        updateStepIndicator();
                    }
                }
                
                async function testCredentials(event) {
                    event.preventDefault();
                    const button = document.getElementById('test-button');
                    button.disabled = true;
                    button.textContent = 'Testing...';
                    
                    const clientId = document.getElementById('client-id').value.trim();
                    const clientSecret = document.getElementById('client-secret').value.trim();
                    
                    // Basic validation
                    if (clientId.length < 20 || clientSecret.length < 20) {
                        showError('Client ID and Secret should be at least 20 characters long');
                        button.disabled = false;
                        button.textContent = 'Test & Save';
                        return;
                    }
                    
                    try {
                        const response = await fetch('/save-config', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                            body: new URLSearchParams({
                                client_id: clientId,
                                client_secret: clientSecret
                            })
                        });
                        
                        const result = await response.json();
                        
                        if (response.ok) {
                            showSuccess('Credentials saved successfully!');
                            setTimeout(() => {
                                nextStep();
                            }, 1000);
                        } else {
                            showError(result.detail || 'Failed to save credentials');
                            button.disabled = false;
                            button.textContent = 'Test & Save';
                        }
                    } catch (error) {
                        showError('Error: ' + error.message);
                        button.disabled = false;
                        button.textContent = 'Test & Save';
                    }
                }
                
                function launchApp() {
                    window.location.href = 'http://127.0.0.1:8888';
                }
            </script>
        </body>
        </html>
        """
    
    @setup_app.post("/save-config")
    async def save_config(
        client_id: str = Form(...),
        client_secret: str = Form(...)
    ):
        """Save Spotify credentials to config file."""
        try:
            # Create config content
            config_content = f"""# Spotify API Credentials
# Generated by Dopetracks Setup Wizard

SPOTIFY_CLIENT_ID={client_id}
SPOTIFY_CLIENT_SECRET={client_secret}
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback

# Database URL (defaults to user data directory)
DATABASE_URL=sqlite:///{DATABASE_DIR / 'local.db'}

# Environment (local app - not a production server)
ENVIRONMENT=development
DEBUG=False
LOG_LEVEL=INFO
"""
            
            # Write config file
            CONFIG_FILE.write_text(config_content)
            logger.info(f"Config saved to {CONFIG_FILE}")
            
            # Basic validation - check if credentials look valid
            if len(client_id) < 20 or len(client_secret) < 20:
                return {"status": "error", "detail": "Credentials appear to be invalid (too short)"}
            
            return {"status": "success", "message": "Configuration saved successfully"}
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return {"status": "error", "detail": str(e)}
    
    # Run setup wizard on port 8889
    def run_setup():
        try:
            uvicorn.run(setup_app, host="127.0.0.1", port=8889, log_level="error")
        except Exception as e:
            logger.error(f"Error running setup wizard: {e}")
    
    setup_thread = threading.Thread(target=run_setup, daemon=True)
    setup_thread.start()
    
    # Wait for server to start
    time.sleep(2)
    
    # Note: Setup wizard runs on port 8889, but native app should handle setup differently
    # For now, log the URL in case manual access is needed
    logger.info("Setup wizard available at http://127.0.0.1:8889")
    print("Setup wizard available at http://127.0.0.1:8889")
    print("(Native app should handle setup through UI)")
    
    # Wait for setup to complete (check config file periodically)
    logger.info("Waiting for setup to complete...")
    print("\n" + "="*60)
    print("Setup wizard opened in your browser.")
    print("Complete the setup there, then this window will continue.")
    print("="*60 + "\n")
    
    # Poll for config completion
    max_wait = 300  # 5 minutes
    wait_time = 0
    while wait_time < max_wait:
        if check_setup_complete():
            logger.info("Setup completed!")
            time.sleep(1)  # Give a moment for final writes
            return True
        time.sleep(2)
        wait_time += 2
    
    logger.warning("Setup wizard timeout - proceeding anyway")
    return False

def launch_main_app():
    """Launch the main Dopetracks application."""
    logger.info("Launching main application...")
    
    # Set environment variables from config
    if CONFIG_FILE.exists():
        from dotenv import load_dotenv
        load_dotenv(CONFIG_FILE, override=True)
        logger.info(f"Loaded config from {CONFIG_FILE}")
    else:
        logger.warning(f"Config file not found at {CONFIG_FILE}")
        print("⚠️  Warning: Config file not found. App may not work correctly.")
    
    # Set database path
    os.environ['DATABASE_URL'] = f"sqlite:///{DATABASE_DIR / 'local.db'}"
    logger.info(f"Database path: {DATABASE_DIR / 'local.db'}")
    
    # Add packages to path
    if IS_BUNDLED:
        # In bundled app, packages should be in APP_DIR
        packages_dir = APP_DIR / 'packages'
    else:
        # In development, use project structure
        packages_dir = APP_DIR / 'packages'
    
    if packages_dir.exists():
        sys.path.insert(0, str(packages_dir))
        logger.info(f"Added {packages_dir} to Python path")
    else:
        logger.error(f"Packages directory not found: {packages_dir}")
        print(f"❌ Error: Packages directory not found at {packages_dir}")
        sys.exit(1)
    
    # Native macOS app - no webview or browser needed
    # Swift app handles all UI
    # Just import and start the API server
    logger.info("Importing application modules (this may take a moment)...")
    try:
        from dopetracks.app import app
        logger.info("Successfully imported app")
    except ImportError as e:
        logger.error(f"Failed to import app: {e}", exc_info=True)
        print("❌ Error: Failed to import application. Check logs for details.")
        print(f"   Error: {e}")
        if IS_BUNDLED:
            print(f"   App directory: {APP_DIR}")
            print(f"   Packages directory: {packages_dir}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error importing app: {e}", exc_info=True)
        print("❌ Error: Application configuration error. Check logs for details.")
        print(f"   Error: {e}")
        sys.exit(1)
    
    logger.info("🚀 Starting Dopetracks API server...")
    
    # Only print to console if not bundled
    if not IS_BUNDLED:
        print("🚀 Starting Dopetracks API Server...")
        print(f"📍 Health check: http://127.0.0.1:8888/health")
        print(f"📁 Logs: {LOG_DIR}")
        print()
    
    # Configure logging for uvicorn
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": str(LOG_DIR / "backend.log"),
                "formatter": "default",
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["file", "console"],
        },
    }
    
    # Check if port is already in use before starting
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 8888))
        sock.close()
    except OSError:
        logger.error("Port 8888 is already in use! Another instance may be running.")
        logger.error("Try: pkill -f 'uvicorn.*app' or lsof -ti :8888 | xargs kill -9")
        if not IS_BUNDLED:
            print("❌ Error: Port 8888 is already in use")
        sys.exit(1)
    
    # Start the server (blocks until stopped)
    try:
        logger.info("Starting uvicorn server...")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8888,
            log_level="info",
            access_log=True,
            log_config=log_config,
        )
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        if not IS_BUNDLED:
            print("\n🛑 Shutting down Dopetracks...")
    except Exception as e:
        logger.error(f"Fatal error in launch_main_app: {e}", exc_info=True)
        import traceback
        logger.error(traceback.format_exc())
        if not IS_BUNDLED:
            print(f"\n❌ Fatal error: {e}")
            print("Check logs for details.")
        sys.exit(1)
    
    # Set up signal handlers for graceful shutdown
    import signal
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        if not IS_BUNDLED:
            print("\n🛑 Shutting down Dopetracks...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    

def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("Dopetracks Launcher")
    logger.info(f"Bundled: {IS_BUNDLED}")
    logger.info(f"App directory: {APP_DIR}")
    logger.info(f"User data directory: {USER_DATA_DIR}")
    logger.info("="*60)
    
    if not check_setup_complete():
        logger.info("First-time setup required")
        print("\n🎵 Welcome to Dopetracks!")
        print("This appears to be your first time running the app.")
        print("Setup wizard will be available at http://127.0.0.1:8889\n")
        
        setup_complete = launch_setup_wizard()
        
        if not setup_complete:
            logger.warning("Setup may not be complete, but proceeding anyway")
            # In bundled app, can't use input() - just proceed
            if IS_BUNDLED:
                logger.info("Proceeding with incomplete setup (bundled app)")
            else:
                response = input("\nSetup may not be complete. Continue anyway? (y/n): ")
                if response.lower() != 'y':
                    logger.info("User cancelled launch")
                    sys.exit(0)
    
    launch_main_app()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal error: {e}")
        print("Check logs for details.")
        sys.exit(1)

