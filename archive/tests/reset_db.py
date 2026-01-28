
"""
Reset database and run fresh migration
"""
import os
from app import create_app, db

def reset_database():
    """Drop all tables and recreate them"""
    app = create_app()
    with app.app_context():
        try:
            print("Dropping all tables...")
            db.drop_all()
            print("Creating all tables...")
            db.create_all()
            print("✅ Database reset completed!")
            print("Now run: python migrate_multi_tenancy.py")
            print("Then run: python test_organization_setup.py")
        except Exception as e:
            print(f"❌ Reset failed: {e}")
            raise

if __name__ == "__main__":
    reset_database()
