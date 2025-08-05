
#!/usr/bin/env python3
"""
Fix screening type table schema to match model requirements
"""
import logging
from app import app, db
from models import ScreeningType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_screening_type_schema():
    """Fix the screening_type table schema"""
    with app.app_context():
        try:
            # Check if gender column exists, if not add it
            result = db.engine.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='screening_type' AND column_name='gender'
            """)
            
            if not result.fetchone():
                logger.info("Adding gender column to screening_type table...")
                db.engine.execute("""
                    ALTER TABLE screening_type 
                    ADD COLUMN gender VARCHAR(10)
                """)
                logger.info("Gender column added successfully")
            else:
                logger.info("Gender column already exists")
            
            # Update any existing records with null gender to support both genders
            db.engine.execute("""
                UPDATE screening_type 
                SET gender = NULL 
                WHERE gender IS NULL OR gender = ''
            """)
            
            db.session.commit()
            logger.info("Screening type schema fix completed successfully")
            
        except Exception as e:
            logger.error(f"Error fixing screening type schema: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    fix_screening_type_schema()
