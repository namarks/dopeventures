import unittest
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys

# The package should be in the Python path after pip install -e .
# No need to manually modify sys.path
from dopetracks.frontend_interface.core_logic import process_user_inputs
from dopetracks.utils import utility_functions as uf

class TestDopeTracksIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment before running tests"""
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        
        # Test data
        cls.test_playlist_name = "Test Playlist"
        cls.test_start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        cls.test_end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get the default messages database path
        try:
            cls.default_db_path = uf.get_messages_db_path()
        except Exception as e:
            logging.warning(f"Could not get default database path: {e}")
            cls.default_db_path = None

    def setUp(self):
        """Set up each test"""
        # Skip tests if environment variables are not set
        required_vars = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            self.skipTest(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        # Skip tests if database file doesn't exist
        if not self.default_db_path or not os.path.exists(self.default_db_path):
            self.skipTest(f"Messages database not found at {self.default_db_path}")

    def test_1_environment_variables(self):
        """Test if required environment variables are set"""
        required_vars = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI']
        for var in required_vars:
            self.assertIsNotNone(os.getenv(var), f"Environment variable {var} is not set")

    def test_2_database_file_exists(self):
        """Test if the messages database file exists"""
        self.assertTrue(os.path.exists(self.default_db_path), 
                       f"Messages database not found at {self.default_db_path}")

    def test_3_process_user_inputs_basic(self):
        """Test basic functionality of process_user_inputs"""
        result = process_user_inputs(
            start_date=self.test_start_date,
            end_date=self.test_end_date,
            playlist_name=self.test_playlist_name
        )
        
        self.assertIsInstance(result, dict, "Result should be a dictionary")
        self.assertIn('status', result, "Result should contain 'status' key")
        self.assertIn('tracks_processed', result, "Result should contain 'tracks_processed' key")

    def test_4_process_user_inputs_invalid_dates(self):
        """Test process_user_inputs with invalid dates"""
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        result = process_user_inputs(
            start_date=future_date,
            end_date=self.test_end_date,
            playlist_name=self.test_playlist_name
        )
        
        self.assertEqual(result['status'], 'error', "Should return error status for future dates")
        self.assertIn('errors', result, "Result should contain 'errors' key")

    def test_5_process_user_inputs_chat_filter(self):
        """Test process_user_inputs with chat name filter"""
        result = process_user_inputs(
            start_date=self.test_start_date,
            end_date=self.test_end_date,
            playlist_name=self.test_playlist_name,
            chat_name_text="test"
        )
        
        self.assertIsInstance(result, dict, "Result should be a dictionary")
        self.assertIn('status', result, "Result should contain 'status' key")

    def test_6_process_user_inputs_custom_filepath(self):
        """Test process_user_inputs with custom filepath"""
        result = process_user_inputs(
            start_date=self.test_start_date,
            end_date=self.test_end_date,
            playlist_name=self.test_playlist_name,
            filepath=self.default_db_path
        )
        
        self.assertIsInstance(result, dict, "Result should be a dictionary")
        self.assertIn('status', result, "Result should contain 'status' key")

if __name__ == '__main__':
    unittest.main() 