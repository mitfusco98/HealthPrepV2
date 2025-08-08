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
            # Check if column already exists
            result = db.session.execute(db.text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'is_root_admin' in columns:
                print("✅ Root admin column already exists")
                return True
            
            # Add the new column
            db.session.execute(db.text("ALTER TABLE users ADD COLUMN is_root_admin BOOLEAN DEFAULT 0 NOT NULL"))
            
            # Also make org_id nullable for root admins
            print("Making org_id nullable for root admins...")
            
            # For SQLite, we need to recreate the table to modify column constraints
            # Get current table schema
            result = db.session.execute(db.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"))
            original_schema = result.fetchone()[0]
            
            # Create backup table
            db.session.execute(db.text("""
                CREATE TABLE users_backup AS SELECT * FROM users
            """))
            
            # Drop original table
            db.session.execute(db.text("DROP TABLE users"))
            
            # Recreate table with nullable org_id
            create_table_sql = """
                CREATE TABLE users (
                    id INTEGER NOT NULL PRIMARY KEY,
                    username VARCHAR(80) NOT NULL,
                    email VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'nurse',
                    is_admin BOOLEAN NOT NULL DEFAULT 0,
                    is_active_user BOOLEAN NOT NULL DEFAULT 1,
                    is_root_admin BOOLEAN NOT NULL DEFAULT 0,
                    org_id INTEGER,
                    epic_user_id VARCHAR(100),
                    two_factor_enabled BOOLEAN DEFAULT 0,
                    session_timeout_minutes INTEGER DEFAULT 30,
                    last_activity DATETIME DEFAULT (datetime('now')),
                    failed_login_attempts INTEGER DEFAULT 0,
                    locked_until DATETIME,
                    created_at DATETIME DEFAULT (datetime('now')),
                    last_login DATETIME DEFAULT (datetime('now')),
                    created_by INTEGER,
                    updated_at DATETIME DEFAULT (datetime('now')),
                    FOREIGN KEY(org_id) REFERENCES organizations (id),
                    FOREIGN KEY(created_by) REFERENCES users (id)
                )
            """
            
            db.session.execute(db.text(create_table_sql))
            
            # Copy data back
            db.session.execute(db.text("""
                INSERT INTO users (id, username, email, password_hash, role, is_admin, is_active_user, 
                                 is_root_admin, org_id, epic_user_id, two_factor_enabled, session_timeout_minutes,
                                 last_activity, failed_login_attempts, locked_until, created_at, last_login, 
                                 created_by, updated_at)
                SELECT id, username, email, password_hash, role, is_admin, is_active_user, 
                       0, org_id, epic_user_id, two_factor_enabled, session_timeout_minutes,
                       last_activity, failed_login_attempts, locked_until, created_at, last_login, 
                       created_by, updated_at
                FROM users_backup
            """))
            
            # Drop backup table
            db.session.execute(db.text("DROP TABLE users_backup"))
            
            # Recreate unique constraints
            db.session.execute(db.text("""
                CREATE UNIQUE INDEX unique_username_per_org ON users(username, org_id) WHERE org_id IS NOT NULL
            """))
            
            db.session.execute(db.text("""
                CREATE UNIQUE INDEX unique_email_per_org ON users(email, org_id) WHERE org_id IS NOT NULL
            """))
            
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