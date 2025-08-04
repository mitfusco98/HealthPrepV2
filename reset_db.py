
"""
Database reset script - drops and recreates all tables
"""

from app import app, db
from models import User, Patient, ScreeningType, Screening, AdminLog
from werkzeug.security import generate_password_hash
from sqlalchemy import inspect
import json

def reset_database():
    """Drop and recreate the database with default data"""
    with app.app_context():
        try:
            # Force drop all tables with CASCADE to handle foreign key constraints
            print("Dropping all tables with CASCADE...")
            
            # Use a more aggressive approach - drop the entire schema and recreate
            with db.engine.connect() as conn:
                # Get all table names with proper quoting for reserved words
                result = conn.execute(db.text("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """))
                table_names = [row[0] for row in result]
                
                if table_names:
                    # Drop all tables at once with CASCADE
                    for table_name in table_names:
                        try:
                            # Quote table names that might be reserved words
                            quoted_name = f'"{table_name}"' if table_name in ['user', 'order', 'group'] else table_name
                            conn.execute(db.text(f"DROP TABLE IF EXISTS {quoted_name} CASCADE"))
                            print(f"Dropped table: {table_name}")
                        except Exception as e:
                            print(f"Warning: Could not drop table {table_name}: {e}")
                    
                    conn.commit()
            
            # Create all tables fresh
            print("Creating all tables...")
            db.create_all()
            print("Database tables created successfully")
            
            # Create default admin user
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            
            # Create a basic user
            basic_user = User(
                username='user',
                email='user@example.com',
                is_admin=False
            )
            basic_user.set_password('user123')
            db.session.add(basic_user)
            
            # Create default screening types
            default_screenings = [
                {
                    'name': 'Mammogram',
                    'description': 'Breast cancer screening',
                    'keywords': json.dumps(['mammogram', 'mammography', 'breast screening']),
                    'gender': 'F',
                    'min_age': 40,
                    'max_age': 75,
                    'frequency_value': 12,
                    'frequency_unit': 'months',
                    'trigger_conditions': json.dumps([]),
                    'is_active': True
                },
                {
                    'name': 'Colonoscopy',
                    'description': 'Colorectal cancer screening',
                    'keywords': json.dumps(['colonoscopy', 'colon screening', 'colorectal']),
                    'gender': None,
                    'min_age': 50,
                    'max_age': 75,
                    'frequency_value': 10,
                    'frequency_unit': 'years',
                    'trigger_conditions': json.dumps([]),
                    'is_active': True
                },
                {
                    'name': 'Pap Smear',
                    'description': 'Cervical cancer screening',
                    'keywords': json.dumps(['pap smear', 'cervical screening', 'cytology']),
                    'gender': 'F',
                    'min_age': 21,
                    'max_age': 65,
                    'frequency_value': 3,
                    'frequency_unit': 'years',
                    'trigger_conditions': json.dumps([]),
                    'is_active': True
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
