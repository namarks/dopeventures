# Multi-Chat Playlist Creation

## Overview

You can now select **multiple chats** when creating a playlist! This is especially useful when:
- You have duplicate chat names (same group chat split into multiple entries)
- You want to combine messages from different time periods
- You want to merge multiple group chats into one playlist

## How It Works

### Backend Support

The `/create-playlist-optimized` endpoint accepts `selected_chat_ids` as a JSON array of integers:

```json
{
  "selected_chat_ids": "[4198, 4387]",
  "playlist_name": "Combined Playlist",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

The backend will:
1. Query Spotify messages from **all selected chats** in the date range
2. Combine all unique Spotify track URLs
3. Create a single playlist with tracks from all selected chats

### Frontend Support

The web interface now supports:
- **Checkbox selection** - Select multiple chats by checking their boxes
- **Chat ID display** - See the unique `chat_id` for each chat entry
- **Recent messages preview** - Help identify which chat entry to use
- **Selection counter** - See how many chats you've selected
- **Multi-select indicator** - Visual feedback that multiple selection is enabled

## Example Use Cases

### 1. Combining Duplicate Chat Entries

If you have two chat entries with the same name (e.g., "dopetracks2025finalfinalFINAL.pdf"):
- **Chat 4198**: Messages from Jan-Oct 2025 (1,986 messages)
- **Chat 4387**: Messages from Oct-Dec 2025 (625 messages)

**Solution:** Select both to get the complete history:
```json
{
  "selected_chat_ids": "[4198, 4387]"
}
```

### 2. Merging Multiple Group Chats

If you have multiple group chats you want to combine:
- "Music Group A" (chat_id: 16)
- "Music Group B" (chat_id: 42)
- "Music Group C" (chat_id: 99)

**Solution:** Select all three:
```json
{
  "selected_chat_ids": "[16, 42, 99]"
}
```

### 3. Time-Based Selection

Select chats based on different time periods:
- Early 2024 chats: `[100, 101, 102]`
- Late 2024 chats: `[200, 201, 202]`

Create separate playlists for each period, or combine them all!

## Benefits

1. **No Data Loss** - Combine split/duplicate chats without missing messages
2. **Flexibility** - Mix and match any chats you want
3. **Efficiency** - One playlist creation instead of multiple
4. **Accuracy** - Uses `chat_id` instead of names (avoids ambiguity)

## Technical Details

### Query Process

When multiple chats are selected, the backend:
1. Queries each chat individually using `chat_id`
2. Filters messages by date range
3. Parses `attributedBody` for binary messages
4. Extracts all Spotify URLs
5. Combines and deduplicates URLs
6. Creates playlist with unique tracks

### Performance

- **Fast**: Uses optimized SQL queries (no upfront processing)
- **Efficient**: Only processes messages in date range
- **Scalable**: Handles multiple chats without performance issues

## UI Features

### Search Results Table

- **Checkbox column**: Select/deselect chats
- **Chat ID column**: See unique identifier
- **Recent messages**: Preview to help identify chats
- **Multi-select header**: Reminder that you can select multiple

### Selected Chats Display

- **Counter**: Shows number of selected chats
- **Badge display**: Each selected chat shown with name and ID
- **Remove button**: Click × to remove individual chats
- **Clear all**: Button to deselect everything

## Tips

1. **Use recent messages** to identify which chat entry you want
2. **Check chat_id** when names are duplicated
3. **Select multiple** if you want to combine histories
4. **Date ranges** apply to all selected chats
5. **Deduplication** happens automatically (same track URL won't appear twice)

## API Example

```bash
curl -X POST "http://localhost:8888/create-playlist-optimized" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "playlist_name=Combined Playlist" \
  -F "start_date=2024-01-01" \
  -F "end_date=2024-12-31" \
  -F "selected_chat_ids=[4198, 4387]"
```

## See Also

- [CHAT_SELECTION_GUIDE.md](./CHAT_SELECTION_GUIDE.md) - How to identify and select chats
- [TESTING_VIA_SWAGGER.md](./TESTING_VIA_SWAGGER.md) - API testing guide
