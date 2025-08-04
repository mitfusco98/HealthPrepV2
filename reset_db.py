
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
