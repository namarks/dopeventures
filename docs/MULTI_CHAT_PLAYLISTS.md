# Multi-Chat Playlist Creation

## Overview

Select multiple chats when creating a playlist. Useful when:
- A group chat is split across multiple database entries (duplicate names)
- You want to combine songs from different group chats into one playlist

## How It Works

1. Search for chats in the app
2. Select one or more chats by their `chat_id`
3. Set an optional date range
4. Create the playlist -- tracks from all selected chats are combined and deduplicated

### Backend API

The `/create-playlist-optimized` endpoint accepts `selected_chat_ids` as a JSON array:

```json
{
  "selected_chat_ids": "[4198, 4387]",
  "playlist_name": "Combined Playlist",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

The backend queries Spotify messages from all selected chats in the date range, combines unique track URLs, and creates a single playlist.

## Example: Combining Duplicate Chat Entries

If the same group chat appears twice (e.g., "dopetracks2025"):
- **Chat 4198**: Messages from Jan--Oct 2025 (1,986 messages)
- **Chat 4387**: Messages from Oct--Dec 2025 (625 messages)

Select both to get the complete history.

## Tips

- Use `chat_id` to distinguish chats with identical names
- Date ranges apply across all selected chats
- Duplicate tracks are automatically removed

## See Also

- [Chat Selection Guide](./CHAT_SELECTION_GUIDE.md)
- [Testing Guide](./TESTING.md)
