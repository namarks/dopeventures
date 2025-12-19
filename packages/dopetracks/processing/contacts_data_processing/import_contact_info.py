import sys
import sqlite3
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
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


def get_contact_info_by_handle(handle_id: str) -> Optional[Dict[str, Any]]:
    """
    Get contact information (name, photo path) by matching handle ID (phone/email).
    
    Args:
        handle_id: Phone number or email address from Messages handle table
        
    Returns:
        Dict with 'first_name', 'last_name', 'full_name', 'photo_path', 'unique_id' or None
    """
    try:
        contacts_db_path = get_contacts_db_path()
        conn = sqlite3.connect(contacts_db_path)
        
        # Clean handle_id for matching (remove formatting)
        cleaned_handle = clean_phone_number(handle_id) if handle_id else ''
        handle_lower = handle_id.lower() if handle_id else ''
        
        # Try to match by phone number or email
        query = """
            SELECT DISTINCT
                ZABCDRECORD.ZFIRSTNAME as first_name,
                ZABCDRECORD.ZLASTNAME as last_name,
                ZABCDRECORD.ZUNIQUEID as unique_id,
                ZABCDRECORD.ZTHUMBNAILIMAGEDATA as thumbnail_ref,
                ZABCDPHONENUMBER.ZFULLNUMBER as phone_number,
                ZABCDEMAILADDRESS.ZADDRESS as email
            FROM ZABCDRECORD
            LEFT JOIN ZABCDPHONENUMBER ON ZABCDRECORD.Z_PK = ZABCDPHONENUMBER.ZOWNER
            LEFT JOIN ZABCDEMAILADDRESS ON ZABCDRECORD.Z_PK = ZABCDEMAILADDRESS.ZOWNER
            WHERE (
                (ZABCDPHONENUMBER.ZFULLNUMBER IS NOT NULL AND ? LIKE '%' || replace(replace(replace(replace(replace(ZABCDPHONENUMBER.ZFULLNUMBER, ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') || '%')
                OR replace(replace(replace(replace(replace(ZABCDPHONENUMBER.ZFULLNUMBER, ' ', ''), '-', ''), '(', ''), ')', ''), '+', '') LIKE '%' || ? || '%'
            )
            OR (
                ZABCDEMAILADDRESS.ZADDRESS IS NOT NULL 
                AND LOWER(ZABCDEMAILADDRESS.ZADDRESS) = ?
            )
            LIMIT 1
        """
        
        cursor = conn.execute(query, (handle_id, cleaned_handle, handle_lower))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            first_name = row[0] or ''
            last_name = row[1] or ''
            unique_id = row[2]
            thumbnail_ref = row[3]  # May be image data or UUID reference
            
            # Build full name
            if first_name and last_name:
                full_name = f"{first_name} {last_name}"
            elif first_name:
                full_name = first_name
            elif last_name:
                full_name = last_name
            else:
                full_name = None
            
            # Check if photo exists in database or external data
            photo_path = None
            external_photo_uuid = None
            
            if unique_id:
                # First check if there's a shared photo reference in thumbnail
                if thumbnail_ref and len(thumbnail_ref) < 100:
                    # Might be a UUID reference
                    try:
                        uuid_ref = thumbnail_ref.decode('utf-8', errors='ignore').strip('\x00').strip()
                        if '-' in uuid_ref and len(uuid_ref) > 30:
                            external_photo_uuid = uuid_ref
                    except:
                        pass
                
                # Photos are stored in ~/Library/Application Support/AddressBook/Images/
                # (Not in Sources subdirectories) - but this is old format
                images_dir = os.path.join(
                    os.path.expanduser('~'),
                    'Library/Application Support/AddressBook/Images'
                )
                if os.path.exists(images_dir):
                    # Try common image extensions (including no extension)
                    for ext in ['.jpg', '.jpeg', '.png', '.tiff', '']:
                        if ext:
                            potential_path = os.path.join(images_dir, f"{unique_id}{ext}")
                        else:
                            potential_path = os.path.join(images_dir, unique_id)
                        
                        if os.path.exists(potential_path):
                            photo_path = potential_path
                            break
            
            return {
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'photo_path': photo_path,
                'unique_id': unique_id,
                'external_photo_uuid': external_photo_uuid  # UUID reference to external data file
            }
        
        return None
    except Exception as e:
        logging.warning(f"Error getting contact info for handle {handle_id}: {e}")
        return None


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