
"""
Multi-Tenancy Migration Script for HealthPrepV2
Run this script to add organization support to existing database
"""

from app import create_app, db
from sqlalchemy import text
import os
from datetime import datetime

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table"""
    result = db.session.execute(text(f"PRAGMA table_info({table_name});")).fetchall()
    columns = [row[1] for row in result]
    return column_name in columns

def check_table_exists(table_name):
    """Check if a table exists"""
    result = db.session.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")).fetchone()
    return result is not None

def run_migration():
    """Run the complete multi-tenancy migration"""

    app = create_app()
    with app.app_context():
        print("Starting multi-tenancy migration...")

        try:
            # Step 1: Create organizations table
            if not check_table_exists('organizations'):
                print("1. Creating organizations table...")
                db.session.execute(text("""
                    CREATE TABLE organizations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) NOT NULL,
                        display_name VARCHAR(150),
                        address TEXT,
                        contact_email VARCHAR(120),
                        phone VARCHAR(20),
                        epic_client_id VARCHAR(100),
                        epic_client_secret VARCHAR(255),
                        epic_fhir_url VARCHAR(255),
                        epic_environment VARCHAR(20) DEFAULT 'sandbox',
                        setup_status VARCHAR(20) DEFAULT 'incomplete',
                        custom_presets_enabled BOOLEAN DEFAULT 1,
                        auto_sync_enabled BOOLEAN DEFAULT 0,
                        max_users INTEGER DEFAULT 10,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        trial_expires TIMESTAMP
                    );
                """))
                db.session.commit()  # Commit after creating table
                print("   ✓ Organizations table created")

            # Step 2: Create epic_credentials table
            if not check_table_exists('epic_credentials'):
                print("2. Creating epic_credentials table...")
                db.session.execute(text("""
                    CREATE TABLE epic_credentials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        org_id INTEGER NOT NULL,
                        access_token TEXT,
                        refresh_token TEXT,
                        token_expires_at TIMESTAMP,
                        token_scope VARCHAR(255),
                        epic_user_id VARCHAR(100),
                        user_id INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP,
                        FOREIGN KEY (org_id) REFERENCES organizations(id),
                        FOREIGN KEY (user_id) REFERENCES users(id)
                    );
                """))
                db.session.commit()  # Commit after creating table
                print("   ✓ Epic credentials table created")

            # Step 3: Add columns to users table
            if not check_column_exists('users', 'org_id'):
                print("3. Adding columns to users table...")
                db.session.execute(text("ALTER TABLE users ADD COLUMN org_id INTEGER;"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN epic_user_id VARCHAR(100);"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0;"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN session_timeout_minutes INTEGER DEFAULT 30;"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN last_activity TIMESTAMP;"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;"))
                db.session.execute(text("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP;"))
                db.session.commit()  # Commit after adding columns
                
                # Set last_activity to current timestamp for existing users
                current_time = datetime.utcnow().isoformat()
                db.session.execute(text(f"UPDATE users SET last_activity = '{current_time}' WHERE last_activity IS NULL;"))
                db.session.commit()
                print("   ✓ Added columns to users table")

            # Step 4: Add columns to patient table
            if not check_column_exists('patient', 'org_id'):
                print("4. Adding columns to patient table...")
                db.session.execute(text("ALTER TABLE patient ADD COLUMN org_id INTEGER;"))
                db.session.execute(text("ALTER TABLE patient ADD COLUMN epic_patient_id VARCHAR(100);"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to patient table")
                
            # Step 5: Add columns to screening table
            if not check_column_exists('screening', 'org_id'):
                print("5. Adding columns to screening table...")
                db.session.execute(text("ALTER TABLE screening ADD COLUMN org_id INTEGER;"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to screening table")
                
            # Step 6: Add columns to document table
            if not check_column_exists('document', 'org_id'):
                print("6. Adding columns to document table...")
                db.session.execute(text("ALTER TABLE document ADD COLUMN org_id INTEGER;"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to document table")
                
            # Step 7: Add columns to screening_type table
            if not check_column_exists('screening_type', 'org_id'):
                print("7. Adding columns to screening_type table...")
                db.session.execute(text("ALTER TABLE screening_type ADD COLUMN org_id INTEGER;"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to screening_type table")
                
            # Step 8: Add columns to screening_preset table
            if not check_column_exists('screening_preset', 'org_id'):
                print("8. Adding columns to screening_preset table...")
                db.session.execute(text("ALTER TABLE screening_preset ADD COLUMN org_id INTEGER;"))
                db.session.execute(text("ALTER TABLE screening_preset ADD COLUMN preset_scope VARCHAR(20) DEFAULT 'organization';"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to screening_preset table")
                
            # Step 9: Add columns to admin_logs table
            if not check_column_exists('admin_logs', 'org_id'):
                print("9. Adding columns to admin_logs table...")
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN org_id INTEGER;"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN patient_id INTEGER;"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN resource_type VARCHAR(50);"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN resource_id INTEGER;"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN action_details TEXT;"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN session_id VARCHAR(100);"))
                db.session.execute(text("ALTER TABLE admin_logs ADD COLUMN user_agent TEXT;"))
                db.session.commit()  # Commit after adding columns
                print("   ✓ Added columns to admin_logs table")

            # Step 10: Create default organization if it doesn't exist
            result = db.session.execute(text("SELECT COUNT(*) FROM organizations;")).fetchone()
            if result[0] == 0:
                print("10. Creating default organization...")
                db.session.execute(text("""
                    INSERT INTO organizations (name, display_name, contact_email, setup_status, custom_presets_enabled, auto_sync_enabled)
                    VALUES ('Default Organization', 'Default Healthcare Organization', 'admin@healthprep.com', 'live', 1, 0);
                """))
                db.session.commit()  # Commit after creating org
                print("   ✓ Default organization created")

            # Step 11: Update existing data to use default organization (org_id = 1)
            print("11. Migrating existing data to default organization...")
            
            # Check if tables exist and have data before updating
            try:
                if check_table_exists('users'):
                    db.session.execute(text("UPDATE users SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated users to default organization")
                
                if check_table_exists('patient'):
                    db.session.execute(text("UPDATE patient SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated patients to default organization")
                
                if check_table_exists('screening'):
                    db.session.execute(text("UPDATE screening SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated screenings to default organization")
                
                if check_table_exists('document'):
                    db.session.execute(text("UPDATE document SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated documents to default organization")
                
                if check_table_exists('screening_type'):
                    db.session.execute(text("UPDATE screening_type SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated screening types to default organization")
                
                if check_table_exists('screening_preset'):
                    db.session.execute(text("UPDATE screening_preset SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated screening presets to default organization")
                
                if check_table_exists('admin_logs'):
                    db.session.execute(text("UPDATE admin_logs SET org_id = 1 WHERE org_id IS NULL;"))
                    print("   ✓ Migrated admin logs to default organization")
                    
                db.session.commit()  # Commit all data updates
                
            except Exception as e:
                print(f"   ⚠️  Data migration warning: {e}")
                print("   Some tables may not exist yet - this is normal for new installations")

            # Step 12: Create indexes for better performance
            print("12. Creating performance indexes...")
            try:
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_patient_org_id ON patient(org_id);"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_screening_org_id ON screening(org_id);"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_document_org_id ON document(org_id);"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_screening_type_org_id ON screening_type(org_id);"))
                db.session.commit()  # Commit indexes
                print("   ✓ Performance indexes created")
            except Exception as e:
                print(f"   ⚠️  Index creation warning: {e}")

            print("\n✅ Multi-tenancy migration completed successfully!")
            print("\nNext steps:")
            print("1. All existing data has been assigned to 'Default Organization'")
            print("2. Users can now be managed with organization scope")
            print("3. New organizations can be created through the admin interface")
            print("4. Epic credentials can be configured per organization")

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Migration failed: {e}")
            print("\nTroubleshooting:")
            print("- Check if the database file is locked")
            print("- Ensure no other processes are using the database")
            print("- Consider backing up your database before running migration")
            print(f"- Error details: {str(e)}")
            raise

if __name__ == "__main__":
    print("HealthPrepV2 Multi-Tenancy Migration")
    print("====================================")
    print()
    print("This script will:")
    print("• Add organization tables and relationships")
    print("• Update existing models with org_id fields")
    print("• Create a default organization for existing data")
    print("• Migrate existing data to use the default organization")
    print()

    # Auto-confirm for automated environments
    import sys
    if not sys.stdin.isatty():
        print("Running in automated mode - proceeding with migration...")
        run_migration()
    else:
        confirm = input("Are you sure you want to run this migration? (yes/no): ")
        if confirm.lower() == 'yes':
            run_migration()
        else:
            print("Migration cancelled.")
