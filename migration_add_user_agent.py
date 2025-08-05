
"""
Migration script to add user_agent column to admin_logs table
"""
import sqlite3
import os

def add_user_agent_column():
    """Add user_agent column to admin_logs table if it doesn't exist"""
    db_path = 'instance/healthprep.db'
    
    if not os.path.exists(db_path):
        print("Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if user_agent column exists
        cursor.execute("PRAGMA table_info(admin_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'user_agent' not in columns:
            print("Adding user_agent column to admin_logs table...")
            cursor.execute("ALTER TABLE admin_logs ADD COLUMN user_agent TEXT")
            conn.commit()
            print("Successfully added user_agent column")
        else:
            print("user_agent column already exists")
            
    except Exception as e:
        print(f"Error adding column: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_user_agent_column()
