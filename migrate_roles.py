#!/usr/bin/env python3
"""
Database migration script to add role and permissions columns.
"""
import os
import sys

# Add the packages directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'packages'))

from packages.dopetracks.dopetracks.database.connection import get_db_session
from sqlalchemy import text

def migrate_add_role_columns():
    """Add role and permissions columns to users table."""
    print("🔄 Adding role and permissions columns to users table...")
    
    with get_db_session() as db:
        try:
            # Add role column with default value
            db.execute(text('ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT "user"'))
            print("✅ Added role column")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️  Role column already exists")
            else:
                print(f"❌ Error adding role column: {e}")
                return False
        
        try:
            # Add permissions column 
            db.execute(text('ALTER TABLE users ADD COLUMN permissions TEXT'))
            print("✅ Added permissions column")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("⚠️  Permissions column already exists")
            else:
                print(f"❌ Error adding permissions column: {e}")
                return False
        
        # Update existing users to have default role
        try:
            result = db.execute(text('UPDATE users SET role = "user" WHERE role IS NULL'))
            updated = result.rowcount
            print(f"✅ Updated {updated} existing users with default role")
        except Exception as e:
            print(f"❌ Error updating existing users: {e}")
            return False
    
    print("🎉 Migration completed successfully!")
    return True

if __name__ == "__main__":
    migrate_add_role_columns() 