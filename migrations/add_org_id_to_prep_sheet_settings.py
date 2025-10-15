"""
Database migration script: Add org_id to prep_sheet_settings table

This migration adds organization scoping to PrepSheetSettings for proper multi-tenancy.

Usage:
    python migrations/add_org_id_to_prep_sheet_settings.py
    
What it does:
    1. Checks if org_id column exists in prep_sheet_settings
    2. If not, adds the column as nullable first
    3. Assigns existing settings to organizations (duplicates for each org)
    4. Makes org_id NOT NULL after data migration
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app, db
from models import PrepSheetSettings, Organization
from sqlalchemy import text, inspect


def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Run the migration"""
    with app.app_context():
        print("=" * 80)
        print("Migration: Add org_id to prep_sheet_settings")
        print("=" * 80)
        
        # Check if org_id column already exists
        if check_column_exists('prep_sheet_settings', 'org_id'):
            print("✓ Column 'org_id' already exists in prep_sheet_settings")
            print("No migration needed.")
            return
        
        print("\n1. Adding org_id column to prep_sheet_settings (nullable)...")
        
        # Add column as nullable first
        db.session.execute(text("""
            ALTER TABLE prep_sheet_settings 
            ADD COLUMN org_id INTEGER REFERENCES organizations(id)
        """))
        db.session.commit()
        print("   ✓ Column added")
        
        print("\n2. Migrating existing settings to organizations...")
        
        # Get all organizations
        organizations = Organization.query.all()
        if not organizations:
            print("   ⚠ No organizations found. Skipping data migration.")
        else:
            # Get existing settings (should be at most one global setting)
            existing_settings = PrepSheetSettings.query.filter_by(org_id=None).all()
            
            if not existing_settings:
                print("   ✓ No existing settings to migrate")
            else:
                print(f"   Found {len(existing_settings)} existing setting(s)")
                
                for setting in existing_settings:
                    # For each organization, create a copy of the setting
                    for org in organizations:
                        new_setting = PrepSheetSettings(
                            org_id=org.id,
                            labs_cutoff_months=setting.labs_cutoff_months,
                            imaging_cutoff_months=setting.imaging_cutoff_months,
                            consults_cutoff_months=setting.consults_cutoff_months,
                            hospital_cutoff_months=setting.hospital_cutoff_months
                        )
                        db.session.add(new_setting)
                        print(f"   ✓ Created settings for organization: {org.name} (ID: {org.id})")
                    
                    # Delete the old global setting
                    db.session.delete(setting)
                    print(f"   ✓ Removed old global setting")
                
                db.session.commit()
                print("   ✓ Data migration complete")
        
        print("\n3. Making org_id NOT NULL...")
        db.session.execute(text("""
            ALTER TABLE prep_sheet_settings 
            ALTER COLUMN org_id SET NOT NULL
        """))
        db.session.commit()
        print("   ✓ Column constraint updated")
        
        print("\n4. Creating index on org_id...")
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_prep_sheet_settings_org_id 
            ON prep_sheet_settings(org_id)
        """))
        db.session.commit()
        print("   ✓ Index created")
        
        print("\n" + "=" * 80)
        print("Migration completed successfully!")
        print("=" * 80)
        print("\nPrepSheetSettings is now organization-scoped for proper multi-tenancy.")


if __name__ == '__main__':
    try:
        migrate()
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
