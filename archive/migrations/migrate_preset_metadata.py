
"""
Migration script to rename metadata column in screening_preset table
to avoid SQLAlchemy conflict with reserved 'metadata' attribute
"""
import sqlite3
import os
from datetime import datetime

def migrate_preset_metadata():
    """Rename metadata column to preset_metadata in screening_preset table"""
    db_path = os.path.join('instance', 'healthprep.db')
    
    if not os.path.exists(db_path):
        print("Database file not found, skipping migration")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if screening_preset table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='screening_preset'
        """)
        
        if not cursor.fetchone():
            print("screening_preset table does not exist, skipping migration")
            conn.close()
            return
        
        # Check if metadata column exists
        cursor.execute("PRAGMA table_info(screening_preset)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'metadata' not in column_names:
            print("metadata column does not exist, skipping migration")
            conn.close()
            return
        
        if 'preset_metadata' in column_names:
            print("preset_metadata column already exists, skipping migration")
            conn.close()
            return
        
        print("Renaming metadata column to preset_metadata...")
        
        # SQLite doesn't support RENAME COLUMN directly, so we need to recreate the table
        # First, get the current table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='screening_preset'")
        original_schema = cursor.fetchone()[0]
        
        # Create new table with updated column name
        new_schema = original_schema.replace('metadata JSON', 'preset_metadata JSON')
        new_table_name = 'screening_preset_new'
        
        cursor.execute(new_schema.replace('screening_preset', new_table_name))
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO screening_preset_new 
            SELECT id, name, description, specialty, shared, screening_data, 
                   metadata as preset_metadata, created_at, updated_at, created_by
            FROM screening_preset
        """)
        
        # Drop old table and rename new table
        cursor.execute("DROP TABLE screening_preset")
        cursor.execute("ALTER TABLE screening_preset_new RENAME TO screening_preset")
        
        conn.commit()
        print("Successfully renamed metadata column to preset_metadata")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_preset_metadata()
