
#!/usr/bin/env python3
"""
Database reset script for HealthPrep Medical Screening System
This script will drop all tables and recreate them with the correct schema
"""

import os
import sys
import logging
from app import create_app, db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    app = create_app()
    
    with app.app_context():
        try:
            # Import all models to ensure they're registered
            import models
            
            logger.info("Dropping all existing tables...")
            db.drop_all()
            
            logger.info("Creating all tables with correct schema...")
            db.create_all()
            
            logger.info("Database reset completed successfully!")
            
            # Create default admin user if it doesn't exist
            from models import User
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
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
            logger.error(f"Error resetting database: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    reset_database()
