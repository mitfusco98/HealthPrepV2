
"""
Database reset script - drops all tables and recreates them
"""

from app import app, db
from models import *
from werkzeug.security import generate_password_hash
import json

def reset_database():
    """Drop all tables and recreate with current schema"""
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating all tables with current schema...")
        db.create_all()
        
        # Create default admin user
        admin_user = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        
        # Create a basic user
        basic_user = User(
            username='user',
            email='user@example.com',
            password_hash=generate_password_hash('user123'),
            is_admin=False
        )
        db.session.add(basic_user)
        
        # Create default screening types
        default_screenings = [
            {
                'name': 'Mammogram',
                'description': 'Breast cancer screening',
                'keywords': json.dumps(['mammogram', 'mammography', 'breast screening']),
                'eligibility_gender': 'F',
                'eligibility_min_age': 40,
                'eligibility_max_age': 75,
                'frequency_value': 1,
                'frequency_unit': 'years',
                'trigger_conditions': json.dumps([])
            },
            {
                'name': 'Colonoscopy',
                'description': 'Colorectal cancer screening',
                'keywords': json.dumps(['colonoscopy', 'colon screening', 'colorectal']),
                'eligibility_gender': None,
                'eligibility_min_age': 50,
                'eligibility_max_age': 75,
                'frequency_value': 10,
                'frequency_unit': 'years',
                'trigger_conditions': json.dumps([])
            },
            {
                'name': 'Pap Smear',
                'description': 'Cervical cancer screening',
                'keywords': json.dumps(['pap smear', 'cervical screening', 'cytology']),
                'eligibility_gender': 'F',
                'eligibility_min_age': 21,
                'eligibility_max_age': 65,
                'frequency_value': 3,
                'frequency_unit': 'years',
                'trigger_conditions': json.dumps([])
            }
        ]
        
        for screening_data in default_screenings:
            screening_type = ScreeningType(**screening_data)
            db.session.add(screening_type)
        
        try:
            db.session.commit()
            print("Database reset successfully!")
            print("Default users created:")
            print("  Admin: username='admin', password='admin123'")
            print("  User: username='user', password='user123'")
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting database: {e}")

if __name__ == '__main__':
    reset_database()
