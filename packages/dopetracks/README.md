# Dopetracks

Dopetracks is a Python library for generating Spotify playlists from iMessage chat databases. It parses iMessage data to extract shared Spotify links and organizes them into playlists.

## Installation

You can install Dopetracks via pip:

```bash
pip install dopetracks

## Usage

```python
from dopetracks.core_logic import process_user_inputs

process_user_inputs(
    start_date="2025-01-01",
    end_date="2025-01-31",
    playlist_name="January Favorites",
    filepath="/path/to/chat.db",
    chat_name_text="My Group Chat"
)
