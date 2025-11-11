"""
Database migration script: Add creation_method to organizations table

This migration adds the creation_method field to track whether organizations
were created via self-service signup or manual root admin creation.

Usage:
    python migrations/add_creation_method_to_organizations.py
    
What it does:
    1. Checks if creation_method column exists in organizations
    2. If not, adds the column with default 'self_service'
    3. Backfills existing organizations with 'self_service'
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from models import Organization
from sqlalchemy import text, inspect

# Create app instance
app = create_app()


def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate():
    """Run the migration"""
    with app.app_context():
        print("=" * 80)
        print("Migration: Add creation_method to organizations")
        print("=" * 80)
        
        # Check if creation_method column already exists
        if check_column_exists('organizations', 'creation_method'):
            print("✓ Column 'creation_method' already exists in organizations")
            print("No migration needed.")
            return
        
        print("\n1. Adding creation_method column to organizations...")
        
        # Add column with default value
        db.session.execute(text("""
            ALTER TABLE organizations 
            ADD COLUMN creation_method VARCHAR(20) DEFAULT 'self_service'
        """))
        db.session.commit()
        print("   ✓ Column added with default 'self_service'")
        
        print("\n2. Backfilling existing organizations...")
        
        # Get count of organizations
        org_count = Organization.query.count()
        
        if org_count == 0:
            print("   ✓ No existing organizations to backfill")
        else:
            # Update all existing organizations to have creation_method='self_service'
            db.session.execute(text("""
                UPDATE organizations 
                SET creation_method = 'self_service' 
                WHERE creation_method IS NULL
            """))
            db.session.commit()
            print(f"   ✓ Backfilled {org_count} organization(s)")
        
        print("\n3. Verifying migration...")
        
        # Verify column exists and has correct default
        if check_column_exists('organizations', 'creation_method'):
            print("   ✓ Column creation_method exists")
            
            # Check that all orgs have a value
            orgs_with_null = db.session.execute(text("""
                SELECT COUNT(*) FROM organizations WHERE creation_method IS NULL
            """)).scalar()
            
            if orgs_with_null == 0:
                print("   ✓ All organizations have creation_method set")
            else:
                print(f"   ⚠ Warning: {orgs_with_null} organization(s) have NULL creation_method")
        
        print("\n" + "=" * 80)
        print("Migration completed successfully!")
        print("=" * 80)


def rollback():
    """Rollback the migration"""
    with app.app_context():
        print("=" * 80)
        print("Rollback: Remove creation_method from organizations")
        print("=" * 80)
        
        if not check_column_exists('organizations', 'creation_method'):
            print("✓ Column 'creation_method' does not exist")
            print("No rollback needed.")
            return
        
        print("\nRemoving creation_method column...")
        
        db.session.execute(text("""
            ALTER TABLE organizations 
            DROP COLUMN creation_method
        """))
        db.session.commit()
        print("   ✓ Column removed")
        
        print("\n" + "=" * 80)
        print("Rollback completed successfully!")
        print("=" * 80)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate organization creation_method field')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    if args.rollback:
        rollback()
    else:
        migrate()
