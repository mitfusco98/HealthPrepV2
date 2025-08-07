
#!/usr/bin/env python3
"""
Script to create a test user for HealthPrep Medical Screening System
"""

import logging
from app import create_app, db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_user():
    """Create a test user account"""
    app = create_app()
    
    with app.app_context():
        try:
            from models import User
            
            # Check if user already exists
            existing_user = User.query.filter_by(username='user').first()
            if existing_user:
                logger.info("User 'user' already exists")
                return
            
            # Create test user
            test_user = User(
                username='user',
                email='user@healthprep.com',
                role='nurse',
                is_admin=False,
                is_active=True
            )
            test_user.set_password('user123')
            db.session.add(test_user)
            db.session.commit()
            
            logger.info("Test user created successfully!")
            logger.info("Username: user")
            logger.info("Password: user123")
            logger.info("Role: nurse")
            
        except Exception as e:
            logger.error(f"Error creating test user: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    create_test_user()
