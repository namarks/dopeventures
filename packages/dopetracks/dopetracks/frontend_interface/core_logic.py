import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import pandas as pd
from dopetracks.processing import prepare_data_main
from dopetracks.processing.spotify_interaction import spotify_db_manager as sdm
from dopetracks.utils import utility_functions as uf
from dopetracks.processing.spotify_interaction import create_spotify_playlist as csp
from dopetracks.processing.imessage_data_processing import generate_summary_stats as gss

# Constants
DEFAULT_START_DATE = '2025-01-01'
DEFAULT_END_DATE = '2025-01-05'
DEFAULT_PLAYLIST_NAME = 'tester playlist'
DATE_FORMAT = '%Y-%m-%d'

def validate_dates(start_date: str, end_date: str) -> None:
    """
    Validate date inputs.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Raises:
        ValueError: If dates are invalid or start_date is after end_date
    """
    try:
        start_dt = datetime.strptime(start_date, DATE_FORMAT)
        end_dt = datetime.strptime(end_date, DATE_FORMAT)
        if start_dt > end_dt:
            raise ValueError("start_date must be before or equal to end_date")
    except ValueError as e:
        raise ValueError(f"Invalid date format. Use {DATE_FORMAT} format. Error: {str(e)}")

def process_user_inputs(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    playlist_name: str = DEFAULT_PLAYLIST_NAME,
    filepath: Optional[str] = None,
    selected_chat_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Process user inputs to create a Spotify playlist from iMessage data.
    
    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        playlist_name (str): Name of the Spotify playlist to create
        filepath (Optional[str]): Custom path to messages database
        selected_chat_names (Optional[List[str]]): List of specific chat names to filter by
        
    Returns:
        Dict[str, Any]: Dictionary containing:
            - status: 'success', 'warning', or 'error'
            - playlist_name: Name of the created playlist
            - tracks_processed: Number of tracks processed
            - errors: List of error messages if any
            - summary: Optional summary statistics
            
    Raises:
        ValueError: If dates are invalid or start_date is after end_date
        FileNotFoundError: If messages database file is not found
    """
    try:
        # Validate dates
        validate_dates(start_date, end_date)

        # Initialize result dictionary
        result = {
            'status': 'success',
            'playlist_name': playlist_name,
            'tracks_processed': 0,
            'errors': []
        }

        # Get messages database path
        if filepath:
            messages_db_path = filepath
            logging.info(f"Using input filepath: {messages_db_path}")
        else:
            messages_db_path = uf.get_messages_db_path()
            logging.info(f"Using default messages_db_path: {messages_db_path}")

        # Step 1: Pull and clean data
        try:
            data = prepare_data_main.pull_and_clean_messages(messages_db_path)
        except Exception as e:
            logging.error(f"Error pulling and cleaning messages: {str(e)}")
            result['status'] = 'error'
            result['errors'].append(f"Data processing error: {str(e)}")
            return result

        # Step 2: Get Spotify URL metadata and cache URLs
        try:
            sdm.main(data['messages'], 'all_spotify_links')
        except Exception as e:
            logging.error(f"Error processing Spotify URLs: {str(e)}")
            result['status'] = 'error'
            result['errors'].append(f"Spotify URL processing error: {str(e)}")
            return result

        # Step 3: Create Spotify playlist and add tracks
        filtered_messages = data['messages'][
            (data['messages']['date'] >= start_date) &
            (data['messages']['date'] <= end_date) &
            (data['messages']['spotify_song_links'].apply(len) > 0)
        ]

        # Apply chat name filter if provided
        if selected_chat_names:
            logging.info(f"Filtering messages by selected chats: {selected_chat_names}")
            filtered_messages = filtered_messages[
                filtered_messages['chat_name'].apply(
                    lambda x: isinstance(x, str) and any(
                        chat_name.lower() in x.lower() for chat_name in selected_chat_names
                    )
                )
            ]
            result['selected_chats'] = selected_chat_names

        # Extract unique Spotify song links
        track_original_urls_list = (
            filtered_messages
            .explode('spotify_song_links')['spotify_song_links']
            .unique()
            .tolist()
        )
        
        result['tracks_processed'] = len(track_original_urls_list)
        
        if not track_original_urls_list:
            logging.warning("No tracks found for the specified criteria")
            result['status'] = 'warning'
            result['errors'].append("No tracks found for the specified criteria")
            return result

        try:
            csp.main(playlist_name, track_original_urls_list)
        except Exception as e:
            logging.error(f"Error creating Spotify playlist: {str(e)}")
            result['status'] = 'error'
            result['errors'].append(f"Playlist creation error: {str(e)}")
            return result

        # Step 4: Generate summary statistics
        try:
            summary = gss.main(data)
            result['summary'] = summary
        except Exception as e:
            logging.error(f"Error generating summary statistics: {str(e)}")
            result['status'] = 'warning'
            result['errors'].append(f"Summary statistics error: {str(e)}")

        return result

    except Exception as e:
        logging.error(f"Unexpected error in process_user_inputs: {str(e)}")
        return {
            'status': 'error',
            'errors': [f"Unexpected error: {str(e)}"]
        }

if __name__ == '__main__':
    process_user_inputs()