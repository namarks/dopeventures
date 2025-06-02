#!/usr/bin/env python3
"""
Reset a user's password to a known value.
"""
import os
import sys

# Add the packages directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'packages'))

from packages.dopetracks.dopetracks.database.connection import get_db_session
from packages.dopetracks.dopetracks.database.models import User
from packages.dopetracks.dopetracks.auth.security import hash_password

def reset_user_password(username: str, new_password: str):
    """Reset a user's password."""
    
    with get_db_session() as db:
        try:
            # Find user
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"❌ User '{username}' not found.")
                return False
            
            # Hash the new password
            hashed_password = hash_password(new_password)
            
            # Update password
            user.password_hash = hashed_password
            
            print(f"✅ Password updated for user '{username}'")
            print(f"📝 New password: {new_password}")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting password: {e}")
            return False

def main():
    """Main function."""
    print("🔑 Dopetracks Password Reset Tool")
    print("=" * 40)
    
    if len(sys.argv) == 1:
        # Interactive mode
        username = input("Enter username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return
        
        password = input("Enter new password: ").strip()
        if not password:
            print("Password cannot be empty.")
            return
        
        reset_user_password(username, password)
    
    elif len(sys.argv) == 3:
        # Command line mode: reset_password.py username password
        username = sys.argv[1]
        password = sys.argv[2]
        reset_user_password(username, password)
    
    else:
        print("Usage:")
        print("  python reset_password.py                    # Interactive mode")
        print("  python reset_password.py <username> <password>  # Direct mode")
        print("\nExample:")
        print("  python reset_password.py nick MyPassword123!")

if __name__ == "__main__":
    main() 