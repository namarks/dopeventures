from typing import Optional
import logging
import time
import dopetracks.processing.imessage_data_processing.data_pull as dp
import dopetracks.processing.imessage_data_processing.data_cleaning as dc 
import dopetracks.processing.imessage_data_processing.data_enrichment as de
import dopetracks.processing.spotify_interaction.spotify_db_manager as sdm
import dopetracks.processing.contacts_data_processing.import_contact_info as ici

# Configure logging with timestamps
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'  # Optional: Customize the timestamp format
)


def pull_and_clean_messages(db_path: Optional[str] = None):
    """
    Main function to pull and clean iMessage data from the specified database.
    Args:
        db_path (Optional[str]): Path to the iMessage database file. If not provided, defaults to "/Users/nmarks/Library/Messages/chat.db".
    Returns:
        dict: A dictionary containing the following datasets:
            - "messages": DataFrame containing cleaned and enriched message data.
            - "handles": DataFrame containing handle data.
            - "chat_message_join": DataFrame containing chat-message join data.
            - "chat_handle_join": DataFrame containing chat-handle join data.
            - "attachments": DataFrame containing attachment data.
    Raises:
        Exception: If an error occurs during the data pulling, cleaning, or enrichment process.
    Logging:
        Logs various stages of the data pulling, cleaning, and enrichment process, including time taken for each stage.
    """
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

        logging.info("Enriching data...")
        messages = de.merge_chat_data(messages, chat_message_join) 
        messages = de.enrich_messages_with_chat_info(messages, handles, chat_handle_join)
        messages = de.add_reaction_type(messages)
        messages['extracted_text'] = messages['attributedBody'].apply(de.parse_AttributeBody)
        messages = de.finalize_text(messages)
        messages = de.append_links_columns(messages, 'final_text')
        data_enriched = time.time()
        logging.info(f"Data successfully enriched! Time taken: {data_enriched - data_cleaned:.2f}s")

        logging.info("Importing contact info...")
        contacts = ici.main()
        contacts_pulled = time.time()
        logging.info(f"Successfully pulled contact info! Time taken: {contacts_pulled - data_enriched:.2f}s")

        # For demonstration, return all datasets as a dictionary
        return {
            "messages": messages,
            "handles": handles,
            "chat_message_join": chat_message_join,
            "chat_handle_join": chat_handle_join,
            "attachments": attachments,
            "contacts": contacts
        }
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        if conn_messages:
            conn_messages.close()
            logging.info("Messages database connection (chat.db) closed.")

        logging.info(
f'''
----------------------------------------------------------
[1] COMPLETED Pulling and cleaning iMessage data
    (Time taken: {data_enriched - start_time:.2f}s)"
----------------------------------------------------------
''')


if __name__ == "__main__":
    data = pull_and_clean_messages()