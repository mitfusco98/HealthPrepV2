
#!/usr/bin/env python3
"""
Database reset script for HealthPrep Medical Screening System
This script will completely remove and recreate the database with the correct schema
"""

import os
import sys
import logging
from app import create_app, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by removing the file and recreating it"""
    app = create_app()
    
    # First, remove the database file if it exists
    db_path = 'healthprep.db'
    instance_db_path = 'instance/healthprep.db'
    
    for path in [db_path, instance_db_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Removed existing database file: {path}")
            except Exception as e:
                logger.warning(f"Could not remove {path}: {e}")
    
    with app.app_context():
        try:
            # Import all models to ensure they're registered
            import models
            
            logger.info("Creating database with correct schema...")
            db.create_all()
            
            logger.info("Database reset completed successfully!")
            
            # Create default admin user
            from models import User
            admin_user = User(
                username='admin',
                email='admin@healthprep.com',
                role='admin',
                is_admin=True,
                is_active=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            logger.info("Default admin user created (username: admin, password: admin123)")
            
        except Exception as e:
            logger.error(f"Error creating database: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    reset_database()
