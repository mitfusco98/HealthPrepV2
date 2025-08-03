
"""
Database initialization script
"""

from app import app, db
from models import User, Patient, ScreeningType, Screening, AdminLog
from werkzeug.security import generate_password_hash
import json

def init_database():
    """Initialize the database with default data"""
    with app.app_context():
        try:
            # Import models first
            import models
            
            # Create all tables
            db.create_all()
            print("Database tables created successfully")
        except Exception as e:
            print(f"Error creating database tables: {e}")
            return
        
        # Create default admin user if it doesn't exist
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin_user)
        
        # Create a basic user if it doesn't exist
        basic_user = User.query.filter_by(username='user').first()
        if not basic_user:
            basic_user = User(
                username='user',
                email='user@example.com',
                password_hash=generate_password_hash('user123'),
                is_admin=False
            )
            db.session.add(basic_user)
        
        # Create some default screening types
        default_screenings = [
            {
                'name': 'Mammogram',
                'description': 'Breast cancer screening',
                'keywords': 'mammogram,mammography,breast screening',
                'eligibility_gender': 'F',
                'eligibility_min_age': 40,
                'eligibility_max_age': 75,
                'frequency_value': 1,
                'frequency_unit': 'years'
            },
            {
                'name': 'Colonoscopy',
                'description': 'Colorectal cancer screening',
                'keywords': 'colonoscopy,colon screening,colorectal',
                'eligibility_gender': None,
                'eligibility_min_age': 50,
                'eligibility_max_age': 75,
                'frequency_value': 10,
                'frequency_unit': 'years'
            },
            {
                'name': 'Pap Smear',
                'description': 'Cervical cancer screening',
                'keywords': 'pap smear,cervical screening,cytology',
                'eligibility_gender': 'F',
                'eligibility_min_age': 21,
                'eligibility_max_age': 65,
                'frequency_value': 3,
                'frequency_unit': 'years'
            }
        ]
        
        for screening_data in default_screenings:
            existing = ScreeningType.query.filter_by(name=screening_data['name']).first()
            if not existing:
                screening_type = ScreeningType(**screening_data)
                db.session.add(screening_type)
        
        try:
            db.session.commit()
            print("Database initialized successfully!")
            print("Default users created:")
            print("  Admin: username='admin', password='admin123'")
            print("  User: username='user', password='user123'")
        except Exception as e:
            db.session.rollback()
            print(f"Error initializing database: {e}")

if __name__ == '__main__':
    init_database()
