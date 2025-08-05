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
            logger.info("Dropping all tables...")

            # For SQLite, we need to disable foreign key constraints first
            with db.engine.connect() as conn:
                conn.execute(db.text("PRAGMA foreign_keys = OFF"))
                conn.commit()

            # Drop all tables
            db.drop_all()
            logger.info("All tables dropped successfully")

            logger.info("Creating all tables...")
            db.create_all()
            logger.info("Database tables created successfully")

            # Re-enable foreign key constraints
            with db.engine.connect() as conn:
                conn.execute(db.text("PRAGMA foreign_keys = ON"))
                conn.commit()

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