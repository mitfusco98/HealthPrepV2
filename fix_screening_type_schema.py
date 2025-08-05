
#!/usr/bin/env python3
"""
Fix screening type table schema to match model requirements
"""
import logging
import os
import sys
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_screening_type_schema():
    """Fix the screening_type table schema"""
    # Get database URL from environment or use default
    database_url = os.environ.get('DATABASE_URL', 'sqlite:///healthprep.db')
    
    try:
        # Create engine directly
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if gender column exists
            if 'sqlite' in database_url.lower():
                # SQLite version
                result = conn.execute(text("PRAGMA table_info(screening_type)"))
                columns = [row[1] for row in result.fetchall()]
                has_gender = 'gender' in columns
            else:
                # PostgreSQL version
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='screening_type' AND column_name='gender'
                """))
                has_gender = result.fetchone() is not None
            
            if not has_gender:
                logger.info("Adding gender column to screening_type table...")
                conn.execute(text("""
                    ALTER TABLE screening_type 
                    ADD COLUMN gender VARCHAR(10)
                """))
                conn.commit()
                logger.info("Gender column added successfully")
            else:
                logger.info("Gender column already exists")
            
            # Update any existing records with null gender to support both genders
            conn.execute(text("""
                UPDATE screening_type 
                SET gender = NULL 
                WHERE gender IS NULL OR gender = ''
            """))
            conn.commit()
        
        logger.info("Screening type schema fix completed successfully")
        
    except Exception as e:
        logger.error(f"Error fixing screening type schema: {str(e)}")
        raise

if __name__ == '__main__':
    fix_screening_type_schema()
