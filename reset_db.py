
import logging
from app import create_app, db
from models import *
from config.settings import initialize_default_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    """Reset the database by dropping and recreating all tables"""
    app = create_app()
    
    with app.app_context():
        try:
            logger.info("Dropping all tables with CASCADE...")
            
            # Get all table names first
            inspector = db.inspect(db.engine)
            table_names = inspector.get_table_names()
            
            # Drop tables with CASCADE to handle foreign key constraints
            with db.engine.connect() as conn:
                for table_name in table_names:
                    try:
                        conn.execute(db.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        logger.info(f"Dropped table: {table_name}")
                    except Exception as e:
                        logger.warning(f"Could not drop table {table_name}: {e}")
                conn.commit()
            
            logger.info("Creating all tables...")
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Ensure ChecklistSettings table has all required columns
            with db.engine.connect() as conn:
                # Check if ChecklistSettings table exists and has correct columns
                try:
                    result = conn.execute(db.text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = 'checklist_settings'
                    """)).fetchall()
                    
                    existing_columns = [row[0] for row in result]
                    required_columns = [
                        'default_status_options', 
                        'default_checklist_items'
                    ]
                    
                    # Check for all required columns including timestamps
                    all_required_columns = [
                        'default_status_options', 
                        'default_checklist_items',
                        'created_at',
                        'updated_at',
                        'updated_by'
                    ]
                    
                    for col in all_required_columns:
                        if col not in existing_columns:
                            if col == 'default_status_options':
                                conn.execute(db.text("""
                                    ALTER TABLE checklist_settings 
                                    ADD COLUMN default_status_options TEXT DEFAULT 'Due\nDue Soon\nComplete\nOverdue'
                                """))
                            elif col == 'default_checklist_items':
                                conn.execute(db.text("""
                                    ALTER TABLE checklist_settings 
                                    ADD COLUMN default_checklist_items TEXT DEFAULT 'Review screening results\nDiscuss recommendations\nSchedule follow-up\nUpdate care plan'
                                """))
                            elif col == 'created_at':
                                conn.execute(db.text("""
                                    ALTER TABLE checklist_settings 
                                    ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                """))
                            elif col == 'updated_at':
                                conn.execute(db.text("""
                                    ALTER TABLE checklist_settings 
                                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                """))
                            elif col == 'updated_by':
                                conn.execute(db.text("""
                                    ALTER TABLE checklist_settings 
                                    ADD COLUMN updated_by INTEGER REFERENCES users(id)
                                """))
                            logger.info(f"Added missing column: {col}")
                    
                    conn.commit()
                    
                except Exception as e:
                    logger.info(f"ChecklistSettings table setup: {e}")
                    pass
            
            # Initialize default data
            try:
                initialize_default_data()
                logger.info("Default data initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing default data: {e}")
            
            logger.info("Database reset successfully!")
            
        except Exception as e:
            logger.error(f"Error resetting database: {e}")
            raise

if __name__ == '__main__':
    reset_database()
