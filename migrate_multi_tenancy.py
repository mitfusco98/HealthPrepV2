"""
Multi-Tenancy Migration Script for HealthPrepV2
Run this script to add organization support to existing database
"""

from app import create_app, db
import os

def run_migration():
    """Run the complete multi-tenancy migration"""

    app = create_app()
    with app.app_context():
        print("Starting multi-tenancy migration...")

        try:
            # Check if organizations table already exists
            result = db.session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organizations';").fetchone()

            if not result:
                print("1. Creating organizations table...")
                db.session.execute("""
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
                """)

            # Check if epic_credentials table already exists
            result = db.session.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='epic_credentials';").fetchone()

            if not result:
                print("2. Creating epic_credentials table...")
                db.session.execute("""
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
                """)

            # Check if org_id column exists in users table
            result = db.session.execute("PRAGMA table_info(users);").fetchall()
            columns = [row[1] for row in result]

            if 'org_id' not in columns:
                print("3. Adding org_id columns to existing tables...")

                # Add columns to users table
                db.session.execute("ALTER TABLE users ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE users ADD COLUMN epic_user_id VARCHAR(100);")
                db.session.execute("ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0;")
                db.session.execute("ALTER TABLE users ADD COLUMN session_timeout_minutes INTEGER DEFAULT 30;")
                db.session.execute("ALTER TABLE users ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                db.session.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0;")
                db.session.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP;")

                # Add org_id to other tables
                db.session.execute("ALTER TABLE patient ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE patient ADD COLUMN epic_patient_id VARCHAR(100);")
                db.session.execute("ALTER TABLE screening ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE document ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE screening_type ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE screening_preset ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE screening_preset ADD COLUMN preset_scope VARCHAR(20) DEFAULT 'organization';")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN org_id INTEGER;")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN patient_id INTEGER;")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN resource_type VARCHAR(50);")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN resource_id INTEGER;")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN action_details TEXT;")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN session_id VARCHAR(100);")
                db.session.execute("ALTER TABLE admin_logs ADD COLUMN user_agent TEXT;")

            # Create default organization if it doesn't exist
            result = db.session.execute("SELECT COUNT(*) FROM organizations;").fetchone()
            if result[0] == 0:
                print("4. Creating default organization...")
                db.session.execute("""
                    INSERT INTO organizations (name, contact_email, setup_status, custom_presets_enabled, auto_sync_enabled)
                    VALUES ('Default Organization', 'admin@healthprep.com', 'live', 1, 0);
                """)

            # Update existing data to use default organization (org_id = 1)
            print("5. Migrating existing data to default organization...")
            db.session.execute("UPDATE users SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE patient SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE screening SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE document SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE screening_type SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE screening_preset SET org_id = 1 WHERE org_id IS NULL;")
            db.session.execute("UPDATE admin_logs SET org_id = 1 WHERE org_id IS NULL;")

            db.session.commit()
            print("✅ Multi-tenancy migration completed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
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

    confirm = input("Are you sure you want to run this migration? (yes/no): ")
    if confirm.lower() == 'yes':
        run_migration()
    else:
        print("Migration cancelled.")