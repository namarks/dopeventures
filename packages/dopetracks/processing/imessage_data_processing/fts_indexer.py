"""
Full-Text Search (FTS) indexer for Messages database.
Creates and maintains a separate FTS database for fast message search.
Legacy helper; prefer the prepared store's built-in FTS when available.
"""
import os
import sqlite3
import pandas as pd
import time
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from . import parsing_utils as pu
from .optimized_queries import convert_to_apple_timestamp

logger = logging.getLogger(__name__)


def get_fts_db_path(source_db_path: str) -> str:
    """Get the path for the FTS database corresponding to a source database."""
    source_path = Path(source_db_path)
    # Store FTS database in same directory with .fts suffix
    fts_path = source_path.parent / f"{source_path.stem}.fts.db"
    return str(fts_path)


def create_fts_database(fts_db_path: str) -> bool:
    """Create FTS database schema. Returns True if successful."""
    try:
        conn = sqlite3.connect(fts_db_path)
        cursor = conn.cursor()
        
        # Create FTS5 virtual table
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS message_text_fts USING fts5(
                message_id UNINDEXED,
                chat_id UNINDEXED,
                date UNINDEXED,
                extracted_text,
                original_text,
                content='',
                content_rowid='rowid'
            )
        """)
        
        # Create regular table for metadata (linked to FTS)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_metadata (
                rowid INTEGER PRIMARY KEY,
                message_id INTEGER NOT NULL,
                chat_id INTEGER,
                date INTEGER,
                is_from_me INTEGER,
                handle_id INTEGER,
                has_attributed_body INTEGER,
                last_updated INTEGER,
                UNIQUE(message_id)
            )
        """)
        
        # Create indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_id 
            ON message_metadata(message_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_date 
            ON message_metadata(chat_id, date)
        """)
        
        # Create table to track indexing status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fts_index_status (
                id INTEGER PRIMARY KEY,
                source_db_path TEXT NOT NULL,
                source_db_hash TEXT,
                last_indexed_date INTEGER,
                total_messages_indexed INTEGER,
                last_updated INTEGER,
                UNIQUE(source_db_path)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Created FTS database at {fts_db_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create FTS database: {e}")
        return False


def get_indexed_message_ids(fts_db_path: str) -> set:
    """Get set of message IDs that are already indexed."""
    try:
        conn = sqlite3.connect(fts_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT message_id FROM message_metadata")
        indexed_ids = {row[0] for row in cursor.fetchall()}
        conn.close()
        return indexed_ids
    except Exception as e:
        logger.warning(f"Could not get indexed message IDs: {e}")
        return set()


def populate_fts_database(
    fts_db_path: str, 
    source_db_path: str, 
    batch_size: int = 1000,
    force_rebuild: bool = False
) -> Dict[str, Any]:
    """
    Extract text from source DB and populate FTS table.
    
    Returns:
        dict with stats: {'total_processed', 'total_indexed', 'errors', 'duration'}
    """
    start_time = time.time()
    stats = {
        'total_processed': 0,
        'total_indexed': 0,
        'errors': 0,
        'duration': 0
    }
    
    try:
        # Ensure FTS database exists
        if not os.path.exists(fts_db_path) or force_rebuild:
            create_fts_database(fts_db_path)
        
        source_conn = sqlite3.connect(source_db_path)
        fts_conn = sqlite3.connect(fts_db_path)
        
        # Get already indexed message IDs (unless force rebuild)
        indexed_ids = set() if force_rebuild else get_indexed_message_ids(fts_db_path)
        
        # Get all messages that need indexing
        query = """
            SELECT 
                message.ROWID as message_id,
                message.text,
                message.attributedBody,
                message.date,
                message.is_from_me,
                message.handle_id,
                chat_message_join.chat_id
            FROM message
            JOIN chat_message_join ON message.ROWID = chat_message_join.message_id
            WHERE (message.text IS NOT NULL OR message.attributedBody IS NOT NULL)
            AND (message.associated_message_type IS NULL OR message.associated_message_type = 0)
            ORDER BY message.date
        """
        
        df = pd.read_sql_query(query, source_conn)
        source_conn.close()
        
        # Filter out already indexed messages
        if indexed_ids:
            df = df[~df['message_id'].isin(indexed_ids)]
        
        total_messages = len(df)
        logger.info(f"Processing {total_messages} messages for FTS indexing...")
        
        if total_messages == 0:
            logger.info("No new messages to index")
            stats['duration'] = time.time() - start_time
            return stats
        
        # Process in batches
        fts_cursor = fts_conn.cursor()
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size].copy()
            stats['total_processed'] += len(batch)
            
            try:
                # Extract text from attributedBody
                batch["parsed_body"] = batch["attributedBody"].apply(pu.parse_attributed_body)

                # Combine text sources
                batch["final_text"] = batch.apply(
                    lambda row: pu.finalize_text(row["text"], row["parsed_body"]),
                    axis=1,
                )
                
                # Insert into FTS table
                for _, row in batch.iterrows():
                    try:
                        final_text = str(row['final_text']) if pd.notna(row['final_text']) else ''
                        original_text = str(row['text']) if pd.notna(row['text']) else ''
                        
                        if final_text:  # Only index non-empty messages
                            fts_cursor.execute("""
                                INSERT INTO message_text_fts 
                                (message_id, chat_id, date, extracted_text, original_text)
                                VALUES (?, ?, ?, ?, ?)
                            """, (
                                int(row['message_id']),
                                int(row['chat_id']) if pd.notna(row['chat_id']) else None,
                                int(row['date']) if pd.notna(row['date']) else None,
                                final_text,
                                original_text
                            ))
                            
                            fts_cursor.execute("""
                                INSERT OR REPLACE INTO message_metadata
                                (message_id, chat_id, date, is_from_me, handle_id, 
                                 has_attributed_body, last_updated)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                int(row['message_id']),
                                int(row['chat_id']) if pd.notna(row['chat_id']) else None,
                                int(row['date']) if pd.notna(row['date']) else None,
                                int(row['is_from_me']) if pd.notna(row['is_from_me']) else 0,
                                int(row['handle_id']) if pd.notna(row['handle_id']) else None,
                                1 if pd.notna(row['attributedBody']) else 0,
                                int(time.time())
                            ))
                            stats['total_indexed'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        logger.debug(f"Error indexing message {row.get('message_id', 'unknown')}: {e}")
                
                fts_conn.commit()
                
                if (i + batch_size) % (batch_size * 10) == 0:
                    logger.info(f"Indexed {min(i+batch_size, len(df))}/{len(df)} messages...")
                    
            except Exception as e:
                logger.error(f"Error processing batch {i}-{i+batch_size}: {e}")
                stats['errors'] += len(batch)
        
        # Update index status
        fts_cursor.execute("""
            INSERT OR REPLACE INTO fts_index_status
            (source_db_path, last_indexed_date, total_messages_indexed, last_updated)
            VALUES (?, ?, ?, ?)
        """, (
            source_db_path,
            int(time.time()),
            stats['total_indexed'],
            int(time.time())
        ))
        fts_conn.commit()
        
        fts_conn.close()
        
        stats['duration'] = time.time() - start_time
        logger.info(f"FTS indexing complete! Indexed {stats['total_indexed']} messages in {stats['duration']:.2f}s")
        
    except Exception as e:
        logger.error(f"Failed to populate FTS database: {e}", exc_info=True)
        stats['errors'] += 1
    
    return stats


def search_fts(
    fts_db_path: str, 
    search_term: str, 
    chat_ids: Optional[List[int]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[int] = None,
    limit: int = 1000
) -> pd.DataFrame:
    """
    Search using FTS - much faster than parsing attributedBody on demand.
    
    Args:
        fts_db_path: Path to FTS database
        search_term: Text to search for
        chat_ids: Optional list of chat IDs to filter by
        start_date: Optional start date (ISO format string)
        end_date: Optional end date (Apple timestamp)
        limit: Maximum number of results
    
    Returns:
        DataFrame with matching messages
    """
    if not os.path.exists(fts_db_path):
        logger.warning(f"FTS database not found at {fts_db_path}")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(fts_db_path)
        
        # Build FTS query - escape special characters
        # FTS5 uses a different syntax, so we need to quote the search term
        escaped_term = search_term.replace('"', '""')
        fts_query = f'extracted_text MATCH "{escaped_term}" OR original_text MATCH "{escaped_term}"'
        params = []
        
        query = f"""
            SELECT 
                m.message_id,
                m.chat_id,
                m.date,
                m.is_from_me,
                m.handle_id,
                fts.extracted_text,
                fts.original_text,
                fts.rank
            FROM message_text_fts fts
            JOIN message_metadata m ON fts.rowid = m.rowid
            WHERE {fts_query}
        """
        
        # Add filters
        conditions = []
        if chat_ids:
            placeholders = ','.join(['?'] * len(chat_ids))
            conditions.append(f"m.chat_id IN ({placeholders})")
            params.extend(chat_ids)
        
        if start_date:
            start_ts = convert_to_apple_timestamp(start_date)
            conditions.append("m.date >= ?")
            params.append(start_ts)
        
        if end_date:
            conditions.append("m.date <= ?")
            params.append(end_date)
        
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        query += f" ORDER BY fts.rank, m.date DESC LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
        
    except Exception as e:
        logger.error(f"FTS search error: {e}", exc_info=True)
        return pd.DataFrame()


def get_fts_status(fts_db_path: str) -> Optional[Dict[str, Any]]:
    """Get status information about the FTS index."""
    if not os.path.exists(fts_db_path):
        return None
    
    try:
        conn = sqlite3.connect(fts_db_path)
        cursor = conn.cursor()
        
        # Get index status
        cursor.execute("SELECT * FROM fts_index_status LIMIT 1")
        status_row = cursor.fetchone()
        
        # Get message count
        cursor.execute("SELECT COUNT(*) FROM message_metadata")
        message_count = cursor.fetchone()[0]
        
        conn.close()
        
        if status_row:
            return {
                'source_db_path': status_row[1],
                'last_indexed_date': status_row[3],
                'total_messages_indexed': status_row[4] or message_count,
                'last_updated': status_row[5]
            }
        else:
            return {
                'total_messages_indexed': message_count
            }
    except Exception as e:
        logger.error(f"Error getting FTS status: {e}")
        return None


def is_fts_available(fts_db_path: str) -> bool:
    """Check if FTS database exists and has data."""
    if not os.path.exists(fts_db_path):
        return False
    
    try:
        conn = sqlite3.connect(fts_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM message_metadata")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

