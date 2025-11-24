"""
Initialize System Organization (org_id=0) for root admin audit logging.
This script can be safely run multiple times - it will only create the org if it doesn't exist.

Production-safe: Uses main.app (guaranteed in production) instead of create_app factory.
"""
from main import app
from app import db
from models import Organization
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_system_organization():
    """Create System Organization (org_id=0) if it doesn't exist"""
    with app.app_context():
        # Check if System Organization exists
        system_org = Organization.query.filter_by(id=0).first()
        
        if system_org:
            logger.info("System Organization (org_id=0) already exists")
            logger.info(f"  Name: {system_org.name}")
            logger.info(f"  Status: {system_org.onboarding_status}")
            return
        
        logger.info("Creating System Organization (org_id=0)...")
        
        # Create System Organization with minimal required fields
        # Most fields will use model defaults
        system_org = Organization(
            name="System Organization",
            display_name="System Organization",
            specialty="System",
            site="System",
            contact_email="system@healthprep.com",
            billing_email="system@healthprep.com"
        )
        
        # Explicitly set ID to 0 after instantiation
        system_org.id = 0
        
        # Set status fields to indicate this is a completed system org
        system_org.onboarding_status = "completed"
        system_org.setup_status = "live"
        system_org.subscription_status = "manual_billing"
        system_org.creation_method = "system"
        system_org.max_users = 1000
        
        db.session.add(system_org)
        db.session.commit()
        
        logger.info("✅ System Organization (org_id=0) created successfully!")
        logger.info("   This organization is used for root admin audit logging")

if __name__ == '__main__':
    try:
        init_system_organization()
    except Exception as e:
        logger.error(f"❌ Error initializing System Organization: {e}")
        raise
