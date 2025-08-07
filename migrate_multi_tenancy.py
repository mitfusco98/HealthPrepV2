"""
Multi-Tenancy Migration Script for HealthPrepV2
Run this script to add organization support to existing database
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import app, db
import os

def create_multi_tenancy_tables():
    """Create new multi-tenancy tables"""
    
    # SQL commands to create new tables
    sql_commands = [
        # Create organizations table
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id SERIAL PRIMARY KEY,
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
            custom_presets_enabled BOOLEAN DEFAULT true,
            auto_sync_enabled BOOLEAN DEFAULT false,
            max_users INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            trial_expires TIMESTAMP
        );
        """,
        
        # Create epic_credentials table
        """
        CREATE TABLE IF NOT EXISTS epic_credentials (
            id SERIAL PRIMARY KEY,
            org_id INTEGER REFERENCES organizations(id) NOT NULL,
            access_token TEXT,
            refresh_token TEXT,
            token_expires_at TIMESTAMP,
            token_scope VARCHAR(255),
            epic_user_id VARCHAR(100),
            user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        );
        """,
        
        # Add org_id columns to existing tables
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS epic_user_id VARCHAR(100);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT false;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS session_timeout_minutes INTEGER DEFAULT 30;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP;",
        
        "ALTER TABLE patient ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE patient ADD COLUMN IF NOT EXISTS epic_patient_id VARCHAR(100);",
        
        "ALTER TABLE screening ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE document ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE screening_type ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        
        "ALTER TABLE screening_preset ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE screening_preset ADD COLUMN IF NOT EXISTS preset_scope VARCHAR(20) DEFAULT 'organization';",
        
        # Update admin_logs for organization scope
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id);",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS patient_id INTEGER REFERENCES patient(id);",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50);",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS resource_id INTEGER;",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS action_details TEXT;",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR(100);",
        "ALTER TABLE admin_logs ADD COLUMN IF NOT EXISTS user_agent TEXT;",
        
        # Create unique constraints for multi-tenancy
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;",
        "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key;",
        "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS unique_username_per_org UNIQUE (username, org_id);",
        "ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS unique_email_per_org UNIQUE (email, org_id);",
        
        "ALTER TABLE patient DROP CONSTRAINT IF EXISTS patient_mrn_key;", 
        "ALTER TABLE patient ADD CONSTRAINT IF NOT EXISTS unique_mrn_per_org UNIQUE (mrn, org_id);",
        
        # Create indexes for better performance
        "CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);",
        "CREATE INDEX IF NOT EXISTS idx_patient_org_id ON patient(org_id);",
        "CREATE INDEX IF NOT EXISTS idx_screening_org_id ON screening(org_id);",
        "CREATE INDEX IF NOT EXISTS idx_document_org_id ON document(org_id);",
        "CREATE INDEX IF NOT EXISTS idx_screening_type_org_id ON screening_type(org_id);",
        "CREATE INDEX IF NOT EXISTS idx_admin_logs_org_id ON admin_logs(org_id);",
    ]
    
    return sql_commands

def create_default_organization():
    """Create a default organization for existing data"""
    
    default_org_sql = """
    INSERT INTO organizations (name, contact_email, setup_status, custom_presets_enabled, auto_sync_enabled)
    VALUES ('Default Organization', 'admin@healthprep.com', 'live', true, false)
    ON CONFLICT DO NOTHING
    RETURNING id;
    """
    
    return default_org_sql

def migrate_existing_data():
    """Migrate existing data to use the default organization"""
    
    migration_sql = [
        # Update users to belong to default org (org_id = 1)
        "UPDATE users SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update patients to belong to default org
        "UPDATE patient SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update screenings to belong to default org
        "UPDATE screening SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update documents to belong to default org
        "UPDATE document SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update screening types to belong to default org
        "UPDATE screening_type SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update admin logs to belong to default org
        "UPDATE admin_logs SET org_id = 1 WHERE org_id IS NULL;",
        
        # Update screening presets to belong to default org
        "UPDATE screening_preset SET org_id = 1 WHERE org_id IS NULL AND shared = false;",
    ]
    
    return migration_sql

def add_not_null_constraints():
    """Add NOT NULL constraints after data migration"""
    
    constraint_sql = [
        "ALTER TABLE users ALTER COLUMN org_id SET NOT NULL;",
        "ALTER TABLE patient ALTER COLUMN org_id SET NOT NULL;", 
        "ALTER TABLE screening ALTER COLUMN org_id SET NOT NULL;",
        "ALTER TABLE document ALTER COLUMN org_id SET NOT NULL;",
        "ALTER TABLE screening_type ALTER COLUMN org_id SET NOT NULL;",
        "ALTER TABLE admin_logs ALTER COLUMN org_id SET NOT NULL;",
    ]
    
    return constraint_sql

def run_migration():
    """Run the complete multi-tenancy migration"""
    
    with app.app_context():
        print("Starting multi-tenancy migration...")
        
        try:
            # 1. Create new tables and add columns
            print("1. Creating multi-tenancy tables and columns...")
            for sql in create_multi_tenancy_tables():
                db.session.execute(sql)
            
            # 2. Create default organization
            print("2. Creating default organization...")
            db.session.execute(create_default_organization())
            
            # 3. Migrate existing data
            print("3. Migrating existing data to default organization...")
            for sql in migrate_existing_data():
                db.session.execute(sql)
            
            # 4. Add NOT NULL constraints
            print("4. Adding NOT NULL constraints...")
            for sql in add_not_null_constraints():
                db.session.execute(sql)
            
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
    print("• Add unique constraints within organizations")
    print("• Enhance audit logging for HIPAA compliance")
    print()
    
    confirm = input("Are you sure you want to run this migration? (yes/no): ")
    if confirm.lower() == 'yes':
        run_migration()
    else:
        print("Migration cancelled.")