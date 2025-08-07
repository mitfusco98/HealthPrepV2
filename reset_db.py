
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
    # First, remove the database files if they exist
    db_paths = ['healthprep.db', 'instance/healthprep.db']
    
    for path in db_paths:
        if os.path.exists(path):
            try:
                # Change permissions to ensure we can delete
                os.chmod(path, 0o666)
                os.remove(path)
                logger.info(f"Removed existing database file: {path}")
            except Exception as e:
                logger.warning(f"Could not remove {path}: {e}")
    
    # Ensure instance directory exists with proper permissions
    instance_dir = 'instance'
    if not os.path.exists(instance_dir):
        os.makedirs(instance_dir, mode=0o755)
        logger.info(f"Created directory: {instance_dir}")
    else:
        # Ensure directory is writable
        os.chmod(instance_dir, 0o755)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Import all models to ensure they're registered
            import models
            
            logger.info("Creating database with correct schema...")
            db.create_all()
            
            # Ensure database file has proper permissions
            db_file = 'instance/healthprep.db'
            if os.path.exists(db_file):
                os.chmod(db_file, 0o666)
            
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
