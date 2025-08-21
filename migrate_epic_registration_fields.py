
#!/usr/bin/env python3
"""
Migration script to add Epic registration fields to Organization model
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models import Organization
from sqlalchemy import text

def migrate_epic_registration_fields():
    """Add Epic registration fields to existing organizations"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if epic_app_name column exists
            result = db.session.execute(text("PRAGMA table_info(organizations)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'epic_app_name' not in columns:
                print("Adding epic_app_name column...")
                db.session.execute(text("ALTER TABLE organizations ADD COLUMN epic_app_name VARCHAR(200)"))
            
            if 'epic_app_description' not in columns:
                print("Adding epic_app_description column...")
                db.session.execute(text("ALTER TABLE organizations ADD COLUMN epic_app_description TEXT"))
            
            if 'epic_registration_status' not in columns:
                print("Adding epic_registration_status column...")
                db.session.execute(text("ALTER TABLE organizations ADD COLUMN epic_registration_status VARCHAR(50) DEFAULT 'not_started'"))
            
            if 'epic_registration_date' not in columns:
                print("Adding epic_registration_date column...")
                db.session.execute(text("ALTER TABLE organizations ADD COLUMN epic_registration_date DATETIME"))
            
            # Update existing organizations to have default registration status
            db.session.execute(text("UPDATE organizations SET epic_registration_status = 'not_started' WHERE epic_registration_status IS NULL"))
            
            db.session.commit()
            print("✅ Epic registration fields migration completed successfully")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    print("Starting Epic registration fields migration...")
    success = migrate_epic_registration_fields()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1)
