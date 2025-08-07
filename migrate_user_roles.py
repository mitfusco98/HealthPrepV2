
"""
Migration script to add role column to users table
"""
import sqlite3
import os
from datetime import datetime

def migrate_user_roles():
    """Add role column to users table if it doesn't exist"""
    db_path = os.path.join('instance', 'healthprep.db')
    
    if not os.path.exists(db_path):
        print("Database file not found. Please run the application first to create the database.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if role column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'role' not in columns:
            print("Adding role column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'nurse' NOT NULL")
            
            # Update existing admin users to have admin role
            cursor.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
            
            # Update remaining users to have nurse role
            cursor.execute("UPDATE users SET role = 'nurse' WHERE is_admin = 0 OR is_admin IS NULL")
            
            conn.commit()
            print("Successfully added role column and updated existing users")
        else:
            print("role column already exists")
        
        # Check for other missing columns that might be needed
        expected_columns = ['id', 'username', 'email', 'password_hash', 'role', 'is_admin', 'is_active_user', 'created_at', 'last_login', 'created_by', 'updated_at']
        
        for col in expected_columns:
            if col not in columns:
                if col == 'created_by':
                    print(f"Adding {col} column...")
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER")
                elif col == 'updated_at':
                    print(f"Adding {col} column...")
                    # Add column without default first, then update with current timestamp
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} DATETIME")
                    cursor.execute(f"UPDATE users SET {col} = CURRENT_TIMESTAMP WHERE {col} IS NULL")
                elif col == 'is_active_user':
                    print(f"Adding {col} column...")
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col} BOOLEAN DEFAULT 1 NOT NULL")
                    
        conn.commit()
        conn.close()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        if conn:
            conn.close()

if __name__ == '__main__':
    migrate_user_roles()
