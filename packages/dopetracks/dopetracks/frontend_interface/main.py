import argparse
import asyncio
from dopetracks.frontend_interface.core_logic import processs_user_inputs

def main():
    # Command-line argument parser
    parser = argparse.ArgumentParser(description="Generate a Spotify playlist from iMessage chat database.")
    parser.add_argument("--start_date", type=str, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end_date", type=str, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--playlist_name", type=str, required=True, help="Name of the Spotify playlist")
    parser.add_argument("--filepath", type=str, required=False, help="Path to the iMessage chat.db file")
    parser.add_argument("--chat_name_text", type=str, required=False, help="Filter messages by chat name")

    args = parser.parse_args()

    # Call the core logic
    processs_user_inputs(args.start_date, args.end_date, args.playlist_name, args.filepath, args.chat_name_text)
    
if __name__ == "__main__":
    main()
