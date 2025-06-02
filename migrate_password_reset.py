#!/usr/bin/env python3
"""
Add password reset table to existing database.
"""
import os
import sys
import sqlite3
from datetime import datetime

# Add the packages directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'packages'))

def migrate_password_reset():
    """Add password reset table to database."""
    
    db_path = "dopetracks_multiuser.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database file {db_path} not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_password_resets'
        """)
        
        if cursor.fetchone():
            print("✅ user_password_resets table already exists")
            conn.close()
            return True
        
        # Create the password reset table
        cursor.execute("""
            CREATE TABLE user_password_resets (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                reset_token VARCHAR(255) NOT NULL UNIQUE,
                expires_at DATETIME NOT NULL,
                used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX idx_reset_token_expires 
            ON user_password_resets (reset_token, expires_at)
        """)
        
        cursor.execute("""
            CREATE INDEX idx_user_resets 
            ON user_password_resets (user_id, created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX ix_user_password_resets_id 
            ON user_password_resets (id)
        """)
        
        cursor.execute("""
            CREATE UNIQUE INDEX ix_user_password_resets_reset_token 
            ON user_password_resets (reset_token)
        """)
        
        conn.commit()
        print("✅ user_password_resets table created successfully")
        
        # Verify the table was created
        cursor.execute("SELECT COUNT(*) FROM user_password_resets")
        print(f"✅ Password reset table verified (0 records)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating password reset table: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Adding password reset table to database...")
    success = migrate_password_reset()
    
    if success:
        print("✅ Password reset migration completed successfully!")
    else:
        print("❌ Password reset migration failed!")
        sys.exit(1) 