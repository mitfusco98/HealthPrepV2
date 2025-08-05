
"""
Database inspection script to see what tables and columns exist
"""

from app import app, db
from sqlalchemy import inspect

def check_database():
    """Check what tables and columns exist in the database"""
    with app.app_context():
        inspector = inspect(db.engine)
        
        print("=== DATABASE TABLES ===")
        tables = inspector.get_table_names()
        for table in tables:
            print(f"\nTable: {table}")
            columns = inspector.get_columns(table)
            for column in columns:
                print(f"  - {column['name']}: {column['type']}")
        
        if not tables:
            print("No tables found in database")

if __name__ == '__main__':
    check_database()
