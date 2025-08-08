#!/usr/bin/env python3
"""
Setup script for creating the first root admin user
"""

from app import create_app, db
from models import User, Organization
import getpass

def setup_root_admin():
    """Create the first root admin user"""
    app = create_app()
    
    with app.app_context():
        print("HealthPrep Root Admin Setup")
        print("=" * 30)
        
        # Check if root admin already exists
        existing_root = User.query.filter_by(is_root_admin=True).first()
        if existing_root:
            print(f"Root admin already exists: {existing_root.username}")
            return
        
        print("Creating the first root admin user...")
        print()
        
        # Get user input
        username = input("Root admin username: ").strip()
        email = input("Root admin email: ").strip()
        
        # Validate input
        if not username or not email:
            print("Error: Username and email are required")
            return
        
        # Check if username/email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        
        if existing_user:
            print("Error: Username or email already exists")
            return
        
        password = getpass.getpass("Root admin password: ")
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("Error: Passwords do not match")
            return
        
        if len(password) < 6:
            print("Error: Password must be at least 6 characters")
            return
        
        try:
            # Create root admin user
            root_admin = User(
                username=username,
                email=email,
                role='root_admin',
                is_admin=True,
                is_root_admin=True,
                is_active_user=True,
                org_id=None  # Root admins don't belong to any organization
            )
            root_admin.set_password(password)
            
            db.session.add(root_admin)
            db.session.commit()
            
            print()
            print("✅ Root admin user created successfully!")
            print(f"Username: {username}")
            print(f"Email: {email}")
            print()
            print("You can now access the root admin dashboard at:")
            print("http://localhost:5000/root-admin/dashboard")
            print()
            print("Next steps:")
            print("1. Start the application: python main.py")
            print("2. Login with your root admin credentials")
            print("3. Create your first organization")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating root admin: {str(e)}")

if __name__ == "__main__":
    setup_root_admin()