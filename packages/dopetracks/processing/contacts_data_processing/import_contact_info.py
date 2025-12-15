import sys
import sqlite3
import logging
import json
import os
from datetime import datetime
import re
import pandas as pd


def get_contacts_db_path():
    """Find the path to the macOS AddressBook SQLite database."""
    sources_dir = os.path.join(
        '/Users', 
        os.environ.get('USER'), 
        'Library/Application Support/AddressBook/Sources'
    )
    
    if not os.path.exists(sources_dir):
        raise FileNotFoundError(f"Sources directory not found: {sources_dir}")

    # Search through subfolders for the first valid database
    for folder in os.listdir(sources_dir):
        db_path = os.path.join(sources_dir, folder, 'AddressBook-v22.abcddb')
        if os.path.exists(db_path):
            return db_path

    raise FileNotFoundError('No AddressBook database found in Sources.')


def check_database_access(db_path):
    """Check if we have access to the Messages database."""
    try:
        with open(db_path, 'rb') as f:
            # Try to read first byte to verify access
            f.read(1)
        return True
    except PermissionError:
        logging.error("PERMISSION_ERROR: Full Disk Access required")
        sys.exit(13)
    except Exception as e:
        logging.error(f"ERROR: {str(e)}")
        sys.exit(1)


def contect_to_contacts_db():
   # Connect to and query contacts database
        conn = sqlite3.connect(get_contacts_db_path())
        cursor = conn.cursor()

        return conn, cursor

def clean_phone_number(phone):
    """Remove non-digit characters from phone number."""
    tmp = re.sub(r'\+1', '', phone) if phone else ''
    return re.sub(r'\D', '', tmp) if phone else ''


def pull_contacts_data(conn):
    contacts_query = """
        SELECT 
            ZABCDRECORD.ZFIRSTNAME as first_name,
            ZABCDRECORD.ZLASTNAME as last_name,
            ZABCDPHONENUMBER.ZFULLNUMBER as phone_number,
            ZABCDEMAILADDRESS.ZADDRESS as email
        FROM ZABCDRECORD
        LEFT JOIN ZABCDPHONENUMBER ON ZABCDRECORD.Z_PK = ZABCDPHONENUMBER.ZOWNER
        LEFT JOIN ZABCDEMAILADDRESS ON ZABCDRECORD.Z_PK = ZABCDEMAILADDRESS.ZOWNER
        WHERE ZABCDRECORD.ZFIRSTNAME IS NOT NULL 
            OR ZABCDRECORD.ZLASTNAME IS NOT NULL
        """
    contacts = pd.read_sql_query(contacts_query, conn)

    contacts['phone_number'] = contacts['phone_number'].apply(clean_phone_number)
    # print(contacts[contacts['first_name'] == 'Mark - Zog Soccer'].head())
    return contacts
     
    

def main():
    contacts_db_path = get_contacts_db_path()
    check_database_access(contacts_db_path)
    conn, cursor = contect_to_contacts_db()
    return pull_contacts_data(conn)

if __name__ == "__main__":
    main()