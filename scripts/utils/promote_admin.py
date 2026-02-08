#!/usr/bin/env python3
"""
Utility script to promote users to admin roles.
Run this to create your first super admin user.
"""
import os
import sys

# Add the packages directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'packages'))

from sqlalchemy.orm import Session
from packages.dopetracks.database.connection import create_session_factory, get_db_session
from packages.dopetracks.database.models import User

def promote_user_to_admin(username: str, role: str = "super_admin"):
    """Promote a user to admin or super_admin role."""
    if role not in ["admin", "super_admin"]:
        print(f"Error: Invalid role '{role}'. Must be 'admin' or 'super_admin'.")
        return False
    
    with get_db_session() as db:
        try:
            # Find user
            user = db.query(User).filter(User.username == username).first()
            if not user:
                print(f"Error: User '{username}' not found.")
                return False
            
            # Update role
            old_role = user.role
            user.role = role
            
            print(f"✅ Successfully promoted user '{username}' from '{old_role}' to '{role}'")
            return True
            
        except Exception as e:
            print(f"Error promoting user: {e}")
            return False

def list_users():
    """List all users and their roles."""    
    with get_db_session() as db:
        try:
            users = db.query(User).order_by(User.created_at).all()
            
            if not users:
                print("No users found.")
                return
            
            print("\n📋 Current Users:")
            print("=" * 60)
            print(f"{'ID':<4} {'Username':<20} {'Role':<12} {'Active':<8} {'Created'}")
            print("-" * 60)
            
            for user in users:
                created = user.created_at.strftime("%Y-%m-%d") if user.created_at else "Unknown"
                status = "Yes" if user.is_active else "No"
                print(f"{user.id:<4} {user.username:<20} {user.role:<12} {status:<8} {created}")
            
            print("-" * 60)
            print(f"Total: {len(users)} users")
            
        except Exception as e:
            print(f"Error listing users: {e}")

def main():
    """Main function."""
    print("🔐 Dopetracks Admin Promotion Tool")
    print("=" * 40)
    
    if len(sys.argv) == 1:
        # Interactive mode
        list_users()
        
        print("\n🚀 Promote a user to admin:")
        username = input("Enter username: ").strip()
        if not username:
            print("Username cannot be empty.")
            return
        
        print("\nAvailable roles:")
        print("1. admin - Can manage users and view system stats")
        print("2. super_admin - Full admin privileges")
        
        role_choice = input("Choose role (1 or 2): ").strip()
        if role_choice == "1":
            role = "admin"
        elif role_choice == "2":
            role = "super_admin"
        else:
            print("Invalid choice.")
            return
        
        confirm = input(f"\nPromote '{username}' to '{role}'? (y/N): ").strip().lower()
        if confirm == 'y':
            promote_user_to_admin(username, role)
        else:
            print("Cancelled.")
    
    elif len(sys.argv) == 2:
        if sys.argv[1] == "list":
            list_users()
        else:
            # Promote user to super_admin by default
            username = sys.argv[1]
            promote_user_to_admin(username, "super_admin")
    
    elif len(sys.argv) == 3:
        # promote_admin.py username role
        username = sys.argv[1]
        role = sys.argv[2]
        promote_user_to_admin(username, role)
    
    else:
        print("Usage:")
        print("  python promote_admin.py                    # Interactive mode")
        print("  python promote_admin.py list               # List all users")
        print("  python promote_admin.py <username>         # Promote to super_admin")
        print("  python promote_admin.py <username> <role>  # Promote to specific role")
        print("\nRoles: admin, super_admin")

if __name__ == "__main__":
    main() 