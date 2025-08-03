
"""
Database reset script - drops and recreates all tables
"""

from app import app, db
from models import User, Patient, ScreeningType, Screening, AdminLog
from werkzeug.security import generate_password_hash
import json

def reset_database():
    """Drop and recreate the database with default data"""
    with app.app_context():
        try:
            # Drop all tables
            print("Dropping all tables...")
            db.drop_all()
            
            # Create all tables fresh
            print("Creating all tables...")
            db.create_all()
            print("Database tables created successfully")
            
            # Create default admin user
            admin_user = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin_user)
            
            # Create a basic user
            basic_user = User(
                username='user',
                email='user@example.com',
                password_hash=generate_password_hash('user123'),
                role='user'
            )
            db.session.add(basic_user)
            
            # Create default screening types
            default_screenings = [
                {
                    'name': 'Mammogram',
                    'description': 'Breast cancer screening',
                    'keywords': json.dumps(['mammogram', 'mammography', 'breast screening']),
                    'eligible_genders': 'F',
                    'min_age': 40,
                    'max_age': 75,
                    'frequency_number': 12,
                    'frequency_unit': 'months'
                },
                {
                    'name': 'Colonoscopy',
                    'description': 'Colorectal cancer screening',
                    'keywords': json.dumps(['colonoscopy', 'colon screening', 'colorectal']),
                    'eligible_genders': 'both',
                    'min_age': 50,
                    'max_age': 75,
                    'frequency_number': 10,
                    'frequency_unit': 'years'
                },
                {
                    'name': 'Pap Smear',
                    'description': 'Cervical cancer screening',
                    'keywords': json.dumps(['pap smear', 'cervical screening', 'cytology']),
                    'eligible_genders': 'F',
                    'min_age': 21,
                    'max_age': 65,
                    'frequency_number': 3,
                    'frequency_unit': 'years'
                }
            ]
            
            for screening_data in default_screenings:
                screening_type = ScreeningType(**screening_data)
                db.session.add(screening_type)
            
            db.session.commit()
            print("Database reset successfully!")
            print("Default users created:")
            print("  Admin: username='admin', password='admin123'")
            print("  User: username='user', password='user123'")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error resetting database: {e}")
            raise

if __name__ == '__main__':
    reset_database()
