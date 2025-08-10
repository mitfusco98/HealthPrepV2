
"""
Migration script to add created_by field to ScreeningType table
"""
import sqlite3
import logging
from app import create_app, db
from models import ScreeningType, User

def migrate_screening_type_created_by():
    """Add created_by column to screening_type table"""
    print("HealthPrepV2 - ScreeningType Created By Migration")
    print("This script will add created_by column to screening_type table")
    
    app = create_app()
    with app.app_context():
        try:
            # Check if created_by column already exists
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('screening_type')]
            
            if 'created_by' in columns:
                print("✓ created_by column already exists in screening_type table")
                return True
            
            print("Adding created_by column to screening_type table...")
            
            # Add the column using raw SQL
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE screening_type ADD COLUMN created_by INTEGER"))
            db.session.commit()
            
            # Get the first admin user to assign as default creator
            admin_user = User.query.filter_by(is_admin=True).first()
            if not admin_user:
                admin_user = User.query.first()
            
            if admin_user:
                print(f"Setting default created_by to user: {admin_user.username}")
                # Update existing records to have a created_by value
                db.session.execute(
                    text("UPDATE screening_type SET created_by = :user_id WHERE created_by IS NULL"),
                    {"user_id": admin_user.id}
                )
                db.session.commit()
            
            print("✓ Migration completed successfully")
            return True
            
        except Exception as e:
            print(f"✗ Migration failed: {str(e)}")
            logging.error(f"ScreeningType created_by migration error: {str(e)}")
            return False

if __name__ == '__main__':
    migrate_screening_type_created_by()
