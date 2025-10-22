#!/usr/bin/env python3
"""
Migration Script: Async Processing & Multi-Tenancy Architecture
Adds new fields to support asynchronous processing, enhanced multi-tenancy, and HIPAA compliance
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from the correct app structure
from app import create_app, db
from models import log_admin_event
from sqlalchemy import text

app = create_app()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_organization_enhancements():
    """Add new fields to Organization model for enhanced multi-tenancy"""
    logger.info("Adding enhanced multi-tenancy fields to Organization model...")
    
    migration_queries = [
        # Production Epic Configuration
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_production_base_url VARCHAR(500);",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_endpoint_id VARCHAR(100);",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_organization_id VARCHAR(100);",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_oauth_url VARCHAR(500);",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS epic_token_url VARCHAR(500);",
        
        # Rate limiting and batch processing settings
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS fhir_rate_limit_per_hour INTEGER DEFAULT 1000;",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS max_batch_size INTEGER DEFAULT 100;",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS async_processing_enabled BOOLEAN DEFAULT TRUE;",
        
        # Audit and compliance settings
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS audit_retention_days INTEGER DEFAULT 2555;",
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS phi_logging_level VARCHAR(20) DEFAULT 'minimal';",
    ]
    
    for query in migration_queries:
        try:
            db.session.execute(text(query))
            logger.info(f"✓ Executed: {query[:50]}...")
        except Exception as e:
            logger.warning(f"Query may have already been applied: {str(e)}")
    
    db.session.commit()
    logger.info("✓ Organization enhancements completed")


def create_async_job_table():
    """Create AsyncJob table for tracking background jobs"""
    logger.info("Creating AsyncJob table...")
    
    create_table_query = """
    CREATE TABLE IF NOT EXISTS async_jobs (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(100) UNIQUE NOT NULL,
        org_id INTEGER REFERENCES organizations(id) NOT NULL,
        user_id INTEGER REFERENCES users(id) NOT NULL,
        job_type VARCHAR(50) NOT NULL,
        status VARCHAR(20) DEFAULT 'queued',
        priority VARCHAR(20) DEFAULT 'normal',
        total_items INTEGER DEFAULT 0,
        completed_items INTEGER DEFAULT 0,
        failed_items INTEGER DEFAULT 0,
        progress_percentage FLOAT DEFAULT 0.0,
        job_data JSONB,
        result_data JSONB,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    );
    """
    
    try:
        db.session.execute(text(create_table_query))
        
        # Create indexes for performance
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_org_id ON async_jobs(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_status ON async_jobs(status);",
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_created_at ON async_jobs(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_job_type ON async_jobs(job_type);"
        ]
        
        for query in index_queries:
            db.session.execute(text(query))
        
        db.session.commit()
        logger.info("✓ AsyncJob table created successfully")
        
    except Exception as e:
        logger.error(f"Error creating AsyncJob table: {str(e)}")
        db.session.rollback()
        raise


def create_fhir_api_call_table():
    """Create FHIRApiCall table for rate limiting and audit"""
    logger.info("Creating FHIRApiCall table...")
    
    create_table_query = """
    CREATE TABLE IF NOT EXISTS fhir_api_calls (
        id SERIAL PRIMARY KEY,
        org_id INTEGER REFERENCES organizations(id) NOT NULL,
        user_id INTEGER REFERENCES users(id),
        endpoint VARCHAR(200) NOT NULL,
        method VARCHAR(10) NOT NULL,
        resource_type VARCHAR(50),
        resource_id VARCHAR(100),
        request_params JSONB,
        response_status INTEGER,
        response_time_ms INTEGER,
        patient_id INTEGER REFERENCES patient(id),
        epic_patient_id VARCHAR(100),
        called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    try:
        db.session.execute(text(create_table_query))
        
        # Create indexes for performance and rate limiting
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_fhir_api_calls_org_id ON fhir_api_calls(org_id);",
            "CREATE INDEX IF NOT EXISTS idx_fhir_api_calls_called_at ON fhir_api_calls(called_at);",
            "CREATE INDEX IF NOT EXISTS idx_fhir_api_calls_org_time ON fhir_api_calls(org_id, called_at);",
            "CREATE INDEX IF NOT EXISTS idx_fhir_api_calls_endpoint ON fhir_api_calls(endpoint);",
            "CREATE INDEX IF NOT EXISTS idx_fhir_api_calls_resource_type ON fhir_api_calls(resource_type);"
        ]
        
        for query in index_queries:
            db.session.execute(text(query))
        
        db.session.commit()
        logger.info("✓ FHIRApiCall table created successfully")
        
    except Exception as e:
        logger.error(f"Error creating FHIRApiCall table: {str(e)}")
        db.session.rollback()
        raise


def enhance_admin_log_table():
    """Enhance AdminLog table for better HIPAA compliance tracking"""
    logger.info("Enhancing AdminLog table for HIPAA compliance...")
    
    enhancement_queries = [
        "ALTER TABLE admin_log ADD COLUMN IF NOT EXISTS resource_type VARCHAR(50);",
        "ALTER TABLE admin_log ADD COLUMN IF NOT EXISTS patient_id INTEGER REFERENCES patient(id);",
        "ALTER TABLE admin_log ADD COLUMN IF NOT EXISTS session_id VARCHAR(100);",
        "ALTER TABLE admin_log ADD COLUMN IF NOT EXISTS user_agent TEXT;",
        "ALTER TABLE admin_log ADD COLUMN IF NOT EXISTS fhir_resource_id VARCHAR(100);",
    ]
    
    for query in enhancement_queries:
        try:
            db.session.execute(text(query))
            logger.info(f"✓ Enhanced AdminLog: {query[:40]}...")
        except Exception as e:
            logger.warning(f"AdminLog enhancement may have already been applied: {str(e)}")
    
    # Add indexes for better performance
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_admin_log_resource_type ON admin_log(resource_type);",
        "CREATE INDEX IF NOT EXISTS idx_admin_log_patient_id ON admin_log(patient_id);",
        "CREATE INDEX IF NOT EXISTS idx_admin_log_session_id ON admin_log(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_admin_log_org_timestamp ON admin_log(org_id, timestamp);"
    ]
    
    for query in index_queries:
        try:
            db.session.execute(text(query))
        except Exception as e:
            logger.warning(f"Index may already exist: {str(e)}")
    
    db.session.commit()
    logger.info("✓ AdminLog table enhanced for HIPAA compliance")


def update_existing_organizations():
    """Update existing organizations with default values for new fields"""
    logger.info("Updating existing organizations with default configurations...")
    
    try:
        from models import Organization
        
        organizations = Organization.query.all()
        
        for org in organizations:
            updated = False
            
            # Set default rate limits if not set
            if org.fhir_rate_limit_per_hour is None:
                org.fhir_rate_limit_per_hour = 1000
                updated = True
            
            if org.max_batch_size is None:
                org.max_batch_size = 100
                updated = True
            
            if org.async_processing_enabled is None:
                org.async_processing_enabled = True
                updated = True
            
            if org.audit_retention_days is None:
                org.audit_retention_days = 2555  # 7 years for HIPAA
                updated = True
            
            if org.phi_logging_level is None:
                org.phi_logging_level = 'minimal'
                updated = True
            
            # Set Epic URLs for sandbox environments
            if org.epic_environment == 'sandbox':
                if not org.epic_oauth_url:
                    org.epic_oauth_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/authorize'
                    updated = True
                
                if not org.epic_token_url:
                    org.epic_token_url = 'https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token'
                    updated = True
            
            if updated:
                db.session.add(org)
                logger.info(f"✓ Updated organization: {org.name}")
        
        db.session.commit()
        logger.info("✓ All existing organizations updated")
        
    except Exception as e:
        logger.error(f"Error updating organizations: {str(e)}")
        db.session.rollback()
        raise


def verify_migration():
    """Verify that all migration changes were applied successfully"""
    logger.info("Verifying migration changes...")
    
    verification_queries = [
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'organizations' AND column_name = 'epic_production_base_url';",
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'organizations' AND column_name = 'fhir_rate_limit_per_hour';",
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'async_jobs';",
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'fhir_api_calls';",
    ]
    
    expected_results = [1, 1, 1, 1]  # Each should return 1 if the column/table exists
    
    for i, query in enumerate(verification_queries):
        try:
            result = db.session.execute(text(query)).scalar()
            if result == expected_results[i]:
                logger.info(f"✓ Verification passed: {query[:50]}...")
            else:
                logger.error(f"✗ Verification failed: {query[:50]}...")
                return False
        except Exception as e:
            logger.error(f"Verification query failed: {str(e)}")
            return False
    
    logger.info("✅ All migration verifications passed!")
    return True


def main():
    """Execute the complete async processing architecture migration"""
    logger.info("Async Processing & Multi-Tenancy Architecture Migration")
    logger.info("=" * 60)
    
    with app.app_context():
        try:
            # Step 1: Enhance Organization model
            migrate_organization_enhancements()
            
            # Step 2: Create AsyncJob table
            create_async_job_table()
            
            # Step 3: Create FHIRApiCall table
            create_fhir_api_call_table()
            
            # Step 4: Enhance AdminLog table
            enhance_admin_log_table()
            
            # Step 5: Update existing organizations
            update_existing_organizations()
            
            # Step 6: Verify migration
            if verify_migration():
                logger.info("\n" + "=" * 60)
                logger.info("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
                logger.info("")
                logger.info("Architectural Enhancements Added:")
                logger.info("1. ✓ Enhanced Organization Model")
                logger.info("   - Production Epic FHIR endpoint configuration")
                logger.info("   - Rate limiting and batch processing controls")
                logger.info("   - HIPAA-compliant audit settings")
                logger.info("")
                logger.info("2. ✓ AsyncJob Table")
                logger.info("   - Background job tracking and monitoring")
                logger.info("   - Progress reporting and status management")
                logger.info("   - Job result storage and error handling")
                logger.info("")
                logger.info("3. ✓ FHIRApiCall Table")
                logger.info("   - API call rate limiting and monitoring")
                logger.info("   - HIPAA-compliant audit trail for FHIR operations")
                logger.info("   - Performance tracking and optimization data")
                logger.info("")
                logger.info("4. ✓ Enhanced AdminLog Table")
                logger.info("   - Improved HIPAA compliance tracking")
                logger.info("   - Session and resource-specific logging")
                logger.info("   - Enhanced patient data access auditing")
                logger.info("")
                logger.info("🚀 System ready for production Epic SMART on FHIR integration!")
                logger.info("   - Multi-tenant organization support")
                logger.info("   - Asynchronous batch processing (500+ patients)")
                logger.info("   - HIPAA-compliant audit logging")
                logger.info("   - Rate limiting and performance monitoring")
                
                # Log the migration completion
                try:
                    log_admin_event(
                        event_type='system_migration_completed',
                        user_id=1,  # System user
                        org_id=None,
                        ip='127.0.0.1',
                        data={
                            'migration_type': 'async_processing_architecture',
                            'completion_time': datetime.utcnow().isoformat(),
                            'components_added': ['async_jobs', 'fhir_api_calls', 'organization_enhancements', 'admin_log_enhancements']
                        },
                        action_details="Completed async processing and multi-tenancy architecture migration"
                    )
                except Exception as e:
                    logger.warning(f"Could not log migration event: {str(e)}")
                
                return True
            else:
                logger.error("Migration verification failed!")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            db.session.rollback()
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)