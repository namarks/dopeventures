# Prepared iMessage Store

Incremental pipeline that builds a persistent, indexed SQLite store for messages and contacts.

## Schema
- `messages`: `message_id` (ROWID), `chat_id`, `date` (UTC string), `sender_handle`, `is_from_me`, `text`, `has_spotify_link`, `spotify_url`, `content_hash`
- `messages_fts`: FTS5 over `text` (content_rowid = `message_id`)
- `contacts`: `handle_id` (ROWID), `contact_info`, `display_name`, `avatar_path`, `stable_id`, `last_seen`
- `meta`: `db_version`, `last_processed_rowid`, `last_contact_rowid`, `last_full_reindex`

## Incremental ingestion
Use `ingestion.ingest_prepared_store` to append messages/contacts:
```bash
python -m dopetracks.processing.imessage_data_processing.ingestion \
  --source-db ~/Library/Messages/chat.db \
  --base-dir ~/Library/Application\ Support/Dopetracks \
  --batch-size 1000 \
  --contact-batch-size 500
```

Notes:
- Uses `last_processed_rowid` / `last_contact_rowid` checkpoints for idempotent re-runs.
- `--force-rebuild` drops/recreates schema and resets checkpoints (also updates `last_full_reindex`).

## Query helpers
- `get_recent_messages_prepared` / `get_chat_overview` read from the prepared store.
- `filter_chat_ids_by_message_content` uses FTS to scope chats by text content.
- `optimized_queries` functions accept optional `prepared_db_path` to reuse the prepared store instead of reparsing `attributedBody`.

## Dedupe
- Stable IDs: message ROWID, handle ROWID.
- Defensive `content_hash` (text + sender + date) stored on each message.

## Tests
`pytest packages/dopetracks/tests/processing/imessage_data_processing`

