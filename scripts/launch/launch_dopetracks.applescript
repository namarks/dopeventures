-- Dopetracks Launcher Script
-- This script launches the Dopetracks server and opens the browser

on run
    set projectPath to POSIX path of (path to me as string)
    set projectPath to text 1 thru -20 of projectPath -- Remove "launch_dopetracks.app/"
    
    tell application "Terminal"
        activate
        -- Create a new window and run the setup/launch commands
        do script "cd " & quoted form of projectPath & " && source venv/bin/activate && python3 start.py"
    end tell
    
    -- Wait a few seconds for server to start
    delay 5
    
    -- Open browser
    tell application "Safari"
        activate
        open location "http://127.0.0.1:8888"
    end tell
end run

