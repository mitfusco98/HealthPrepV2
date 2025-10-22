
"""
Migration script to fix admin_logs table schema
Adds missing event_type column
"""
import sqlite3
import os
from datetime import datetime

def migrate_admin_logs():
    """Add event_type column to admin_logs table if it doesn't exist"""
    db_path = os.path.join('instance', 'healthprep.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Please run the application first to create the database.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if event_type column exists
        cursor.execute("PRAGMA table_info(admin_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'event_type' not in columns:
            print("Adding event_type column to admin_logs table...")
            cursor.execute("ALTER TABLE admin_logs ADD COLUMN event_type VARCHAR(50)")
            
            # Set a default value for existing records
            cursor.execute("UPDATE admin_logs SET event_type = 'legacy_event' WHERE event_type IS NULL")
            
            conn.commit()
            print("Successfully added event_type column")
        else:
            print("event_type column already exists")
        
        # Check for other missing columns and add them
        expected_columns = ['id', 'timestamp', 'event_type', 'user_id', 'ip_address', 'data']
        
        for col in expected_columns:
            if col not in columns:
                if col == 'data':
                    print(f"Adding {col} column...")
                    cursor.execute(f"ALTER TABLE admin_logs ADD COLUMN {col} JSON")
                elif col == 'ip_address':
                    print(f"Adding {col} column...")
                    cursor.execute(f"ALTER TABLE admin_logs ADD COLUMN {col} VARCHAR(45)")
                    
        conn.commit()
        conn.close()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        if conn:
            conn.close()

if __name__ == '__main__':
    migrate_admin_logs()
