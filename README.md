# Dopetracks Project Repo 

The impetus for this project was a desire to automatically create a Spotify playlist that contained all the songs my friends had sent to eachother in the Dopetracks chat group. 

The solution to this problem turns out to be relatively straightforward once you figure things out: 
1. Extract Apple Messages data from the `chat.db` database stored on your Macbook (/Users/{yourusername}/Library/Messages/chat.db)
2. Find messages containing Spotify links
2. Generate Spotify playlist and populate with identified songs

## Prerequisites

- **macOS only** (requires access to Messages database)
- **Python 3.11+**
- **Spotify Premium account** (required for playlist creation)

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/yourusername/dopeventures.git
cd dopeventures

# Option A: Create local virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Option B: Use external virtual environment (like the author uses)
# python3 -m venv /Users/yourusername/root_code_repo/venvs/dopetracks_env
# source /Users/yourusername/root_code_repo/venvs/dopetracks_env/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Spotify API Setup

1. **Create Spotify Developer App**:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Click "Create App"
   - App Name: "Dopetracks" (or any name)
   - App Description: "Personal playlist creator"
   - Redirect URI: `http://localhost:8888/callback`
   - Check the boxes for Terms of Service
   - Click "Save"

2. **Get Your Credentials**:
   - Copy your **Client ID** and **Client Secret**

3. **Create Environment File**:
   Create a `.env` file in the project root:
   ```bash
   SPOTIFY_CLIENT_ID=your_client_id_here
   SPOTIFY_CLIENT_SECRET=your_client_secret_here
   SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
   ```

### 3. Grant System Permissions (macOS)

**Enable Full Disk Access for Terminal/Python**:
1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **Full Disk Access** from the left sidebar
3. Click the lock icon and enter your password
4. Click the "+" button and add:
   - **Terminal** (if running from Terminal)
   - **Python** (if you have a separate Python.app)
   - Or the specific application you're using

### 4. Configure Frontend

Ensure the frontend is configured to connect to the backend:
```bash
# Check that website/config.js contains the correct backend URL:
echo 'const BASE_URL = "http://localhost:8888";' > website/config.js
```

### 5. Alternative: Upload Database File

If you prefer not to grant full disk access, you can:
1. Manually copy your Messages database: 
   ```bash
   cp ~/Library/Messages/chat.db ./my_messages.db
   ```
2. Use the file upload feature in the web interface

## Local Usage

1. **Start the Backend Server**:
   ```bash
   # Activate your virtual environment
   source venv/bin/activate  # If using local venv
   # OR
   # source /Users/yourusername/root_code_repo/venvs/dopetracks_env/bin/activate  # If using external venv
   
   # Start the FastAPI backend
   uvicorn packages.dopetracks.dopetracks.frontend_interface.web_interface:app --host 0.0.0.0 --port 8888 --reload
   ```

2. **Start the Frontend Server** (in a separate terminal):
   ```bash
   cd website
   python3 -m http.server 8889
   ```

3. **Open Your Browser**:
   - Go to: **http://localhost:8889** (frontend)
   - The backend API runs on http://localhost:8888
   - Follow the setup steps in the interface:
     1. Authorize Spotify
     2. Validate username OR upload database file
     3. Prepare data (processes your message history)
     4. Search for chats and select ones for your playlist
     5. Create playlist with your chosen date range

## Troubleshooting

### Common Issues:

1. **"No module named 'packages'" Error**:
   - Make sure you're running the command from the project root (`dopeventures/`)
   - Ensure virtual environment is activated

2. **"Permission denied" for Messages Database**:
   - Grant Full Disk Access (see setup instructions above)
   - Or use the file upload alternative

3. **Spotify Authorization Fails**:
   - Check your `.env` file has correct credentials
   - Ensure redirect URI in Spotify app matches: `http://localhost:8888/callback`
   - Make sure you're using `localhost:8888`, not `127.0.0.1:8888`

4. **"Address already in use" Error**:
   - Kill existing process: `pkill -f uvicorn`
   - Or use a different port: `--port 8889`

5. **Frontend/Backend Connection Issues**:
   - Ensure frontend is running on port 8889 and backend on port 8888
   - Check that `website/config.js` has the correct `BASE_URL`
   - Verify CORS settings allow requests from localhost:8889

## Security Notes

- Your `.env` file contains sensitive credentials - never commit it to version control
- The Messages database contains personal data - handle with care
- All processing happens locally on your machine

## Caching

This project uses an SQLite database to cache metadata for Spotify URLs, stored in the user's home directory at `~/.spotify_cache/spotify_cache.db`. This ensures efficient reuse of metadata and reduces API calls.

To initialize the cache, simply run the script. The cache directory will be created automatically if it doesn't exist.

The cache file is not included in this repository to ensure user privacy and prevent unnecessary commits.

## Useful resources
- typedstream library to parse Apple-formatted binary https://github.com/dgelessus/python-typedstream
- Other projects that parse iMessage data
    - https://github.com/yortos/imessage-analysis/blob/master/notebooks/imessages-analysis.ipynb
    - https://github.com/caleb531/imessage-conversation-analyzer/tree/167fb9c9a9082df453857f640d60904b30690443
    - BAIB project: https://github.com/arjunpat/treehacks24/blob/eb97a81c97b577e37a85d5dbdfdb2464c9fd7bfa/README.md
- List of music-related APIs: https://musicmachinery.com/music-apis/
