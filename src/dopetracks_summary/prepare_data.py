from typing import Optional
import logging
import time
import dopetracks_summary.data_prep.data_pull as dp
import dopetracks_summary.data_prep.data_cleaning as dc 
import dopetracks_summary.data_prep.data_enrichment as de

# Configure logging with timestamps
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'  # Optional: Customize the timestamp format
)


def pull_and_clean_messages(db_path: Optional[str] = None):
    """Main function to pull data."""
    if db_path is None:
        db_path = "/Users/nmarks/Library/Messages/chat.db"  # Default path

    logging.info(
    '''
    ----------------------------------------------------------
    [1] Pulling and cleaning iMessage data
    ----------------------------------------------------------
    ''')
    logging.info("Connecting to the database...")
    start_time = time.time()
    try:
        conn_messages = dp.connect_to_database(db_path)
        db_connection_established = time.time()
        logging.info(f"Database connection established. Time taken: {db_connection_established - start_time:.2f}s")


        logging.info("Pulling data...")        
        messages = dp.fetch_messages(conn_messages)
        handles = dp.fetch_handles(conn_messages)
        chat_message_join = dp.fetch_chat_message_join(conn_messages)
        chat_handle_join = dp.fetch_chat_handle_join(conn_messages)
        attachments = dp.fetch_attachments(conn_messages)
        data_pulled = time.time()
        logging.info(f"Data successfully pulled! Time taken: {data_pulled - db_connection_established:.2f}s")

        logging.info("Cleaning data...")
        messages, handles = dc.rename_columns(messages, handles)
        messages = dc.convert_timestamps(messages)
        data_cleaned = time.time()
        logging.info(f"Data successfully cleaned! Time taken: {data_cleaned - data_pulled:.2f}s")

        logging.info("Enrich data...")
        messages = de.merge_chat_data(messages, chat_message_join) 
        messages = de.enrich_messages_with_chat_info(messages, handles, chat_handle_join)
        messages = de.add_reaction_type(messages)
        messages['extracted_text'] = messages['attributedBody'].apply(de.parse_AttributeBody)
        messages = de.finalize_text(messages)
        messages = de.append_links_columns(messages, 'final_text')
        data_enriched = time.time()
        logging.info(f"Data successfully enriched! Time taken: {data_enriched - data_cleaned:.2f}s")

        # For demonstration, return all datasets as a dictionary
        return {
            "messages": messages,
            "handles": handles,
            "chat_message_join": chat_message_join,
            "chat_handle_join": chat_handle_join,
            "attachments": attachments,
        }
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        if conn_messages:
            conn_messages.close()
            logging.info("Messages database connection (chat.db) closed.")



if __name__ == "__main__":
    data = pull_and_clean_messages()