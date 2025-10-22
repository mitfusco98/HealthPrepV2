#!/usr/bin/env python3
"""
Migration script to add root admin functionality to existing database
"""

from app import create_app, db
from models import User, Organization
import sqlite3
import os

def migrate_root_admin():
    """Add root admin column to users table"""
    app = create_app()
    
    with app.app_context():
        print("Adding root admin support to database...")
        
        try:
            # Check if column already exists (PostgreSQL compatible)
            result = db.session.execute(db.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND table_schema = 'public'
            """))
            columns = [row[0] for row in result.fetchall()]
            
            if 'is_root_admin' in columns:
                print("✅ Root admin column already exists")
                return True
            
            # Add the new column (PostgreSQL syntax)
            db.session.execute(db.text("ALTER TABLE users ADD COLUMN is_root_admin BOOLEAN DEFAULT FALSE NOT NULL"))
            
            # Make org_id nullable for root admins (PostgreSQL allows this directly)
            print("Making org_id nullable for root admins...")
            db.session.execute(db.text("ALTER TABLE users ALTER COLUMN org_id DROP NOT NULL"))
            
            db.session.commit()
            print("✅ Root admin migration completed successfully!")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {str(e)}")
            return False

def create_root_admin_interactive():
    """Interactively create root admin user"""
    app = create_app()
    
    with app.app_context():
        print("\nCreating Root Admin User")
        print("=" * 25)
        
        # Check if root admin already exists
        existing_root = User.query.filter_by(is_root_admin=True).first()
        if existing_root:
            print(f"✅ Root admin already exists: {existing_root.username}")
            print(f"📧 Email: {existing_root.email}")
            return
        
        # Create root admin with default credentials for testing
        username = "rootadmin"
        email = "admin@healthprep.com"
        password = "rootadmin123"
        
        print(f"Creating default root admin user:")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print()
        
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
            
            print("✅ Root admin user created successfully!")
            print()
            print("🎯 Access the root admin dashboard at:")
            print("   http://localhost:5000/root-admin/dashboard")
            print()
            print("📋 Login credentials:")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            print()
            print("⚠️  Remember to change the password after first login!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating root admin: {str(e)}")

if __name__ == "__main__":
    print("HealthPrep Root Admin Setup")
    print("=" * 30)
    
    # Run migration
    if migrate_root_admin():
        # Create root admin user
        create_root_admin_interactive()
    else:
        print("❌ Migration failed, cannot create root admin user")