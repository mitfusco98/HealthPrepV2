
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
        
        # Use SQLAlchemy 2.0+ compatible syntax
        try:
            # Try to drop all tables with proper CASCADE handling
            with db.engine.begin() as conn:
                # Drop all tables with CASCADE to handle foreign key constraints
                conn.execute(db.text("DROP SCHEMA public CASCADE"))
                conn.execute(db.text("CREATE SCHEMA public"))
                conn.execute(db.text("GRANT ALL ON SCHEMA public TO postgres"))
                conn.execute(db.text("GRANT ALL ON SCHEMA public TO public"))
            print("Schema reset successful using CASCADE method")
        except Exception as e:
            print(f"Schema reset method failed: {e}")
            try:
                # Alternative: Drop tables individually in the right order
                with db.engine.begin() as conn:
                    # Drop tables that depend on others first
                    tables_to_drop = [
                        'admin_logs',
                        'ocr_processing_stats', 
                        'phi_filter_settings',
                        'checklist_settings',
                        'conditions',
                        'visits',
                        'medical_documents',
                        'screenings',
                        'screening_variants',
                        'screening_types',
                        'patients',
                        'users'
                    ]
                    
                    for table in tables_to_drop:
                        try:
                            conn.execute(db.text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                        except Exception as table_error:
                            print(f"Warning: Could not drop table {table}: {table_error}")
                            
                print("Individual table drop completed")
            except Exception as e2:
                print(f"Individual table drop also failed: {e2}")
                # Last resort: try db.drop_all() anyway
                try:
                    db.drop_all()
                    print("db.drop_all() worked")
                except Exception as e3:
                    print(f"All drop methods failed: {e3}")
                    return
        
        print("Creating all tables with current schema...")
        db.create_all()
        
        # Create default admin user
        admin_user = User(
            username='admin',
            email='admin@example.com',
            first_name='System',
            last_name='Administrator',
            role='admin',
            is_active=True
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        
        # Create a basic user
        basic_user = User(
            username='user',
            email='user@example.com',
            first_name='Demo',
            last_name='User',
            role='user',
            is_active=True
        )
        basic_user.set_password('user123')
        db.session.add(basic_user)
        
        # Create default screening types
        default_screenings = [
            {
                'name': 'Mammogram',
                'description': 'Breast cancer screening',
                'keywords': json.dumps(['mammogram', 'mammography', 'breast screening']),
                'eligible_genders': json.dumps(['F']),
                'min_age': 40,
                'max_age': 75,
                'frequency_years': 1,
                'trigger_conditions': json.dumps([])
            },
            {
                'name': 'Colonoscopy',
                'description': 'Colorectal cancer screening',
                'keywords': json.dumps(['colonoscopy', 'colon screening', 'colorectal']),
                'eligible_genders': json.dumps(['M', 'F']),
                'min_age': 50,
                'max_age': 75,
                'frequency_years': 10,
                'trigger_conditions': json.dumps([])
            },
            {
                'name': 'Pap Smear',
                'description': 'Cervical cancer screening',
                'keywords': json.dumps(['pap smear', 'cervical screening', 'cytology']),
                'eligible_genders': json.dumps(['F']),
                'min_age': 21,
                'max_age': 65,
                'frequency_years': 3,
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
