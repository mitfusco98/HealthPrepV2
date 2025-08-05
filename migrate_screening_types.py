
#!/usr/bin/env python3
"""
Migration script to update ScreeningType model:
- Remove description column
- Rename gender_restriction to gender
"""

from app import app, db
from models import ScreeningType
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_screening_types():
    """Migrate ScreeningType table schema"""
    with app.app_context():
        try:
            # Check if we need to perform migration
            with db.engine.connect() as conn:
                # Check if gender_restriction column exists
                result = conn.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='screening_type' AND column_name='gender_restriction'
                """)
                has_gender_restriction = result.fetchone() is not None
                
                # Check if description column exists
                result = conn.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='screening_type' AND column_name='description'
                """)
                has_description = result.fetchone() is not None
                
                if has_gender_restriction:
                    logger.info("Renaming gender_restriction to gender...")
                    conn.execute("ALTER TABLE screening_type RENAME COLUMN gender_restriction TO gender")
                    conn.commit()
                    logger.info("✓ Renamed gender_restriction to gender")
                
                if has_description:
                    logger.info("Removing description column...")
                    conn.execute("ALTER TABLE screening_type DROP COLUMN description")
                    conn.commit()
                    logger.info("✓ Removed description column")
                
                if not has_gender_restriction and not has_description:
                    logger.info("Migration already completed or not needed")
                
            logger.info("Migration completed successfully")
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    migrate_screening_types()
