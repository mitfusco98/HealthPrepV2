#!/usr/bin/env python3

"""
Create default admin user for HealthPrep system
"""

import logging
from app import create_app, db
from models import User

def create_default_user():
    """Create default admin user"""
    app = create_app()
    
    with app.app_context():
        # Check if admin user already exists
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            print("Admin user already exists")
            return
        
        # Create admin user
        admin = User(
            username='admin',
            email='admin@healthprep.com',
            password_hash='',
            role='admin'
        )
        admin.set_password('admin123')
        
        # Create regular user for testing
        test_user = User(
            username='test',
            email='test@healthprep.com', 
            password_hash='',
            role='user'
        )
        test_user.set_password('test123')
        
        try:
            db.session.add(admin)
            db.session.add(test_user)
            db.session.commit()
            
            print("Default users created successfully:")
            print("- Admin: admin / admin123")
            print("- Test User: test / test123")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating default users: {e}")

if __name__ == '__main__':
    create_default_user()